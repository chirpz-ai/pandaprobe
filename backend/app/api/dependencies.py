"""Unified request-context dependencies for all API routes.

Management endpoints depend on ``get_api_context`` (Bearer JWT only).
Data-plane endpoints depend on ``require_project``, which accepts
either a Bearer JWT with ``X-Project-ID`` or an org-scoped API key
with ``X-Project-Name``.

API keys are org-scoped.  The caller provides ``X-Project-Name`` at
runtime; the server resolves the project by name within the org and
auto-creates it if it doesn't exist.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID

import structlog
from fastapi import Depends, Request
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.context import ApiContext, AuthMethod
from app.infrastructure.auth.adapters import get_auth_adapter
from app.infrastructure.db.engine import get_db_session
from app.infrastructure.db.repositories.identity_repo import IdentityRepository
from app.infrastructure.db.repositories.project_repo import ProjectRepository
from app.infrastructure.db.repositories.user_repo import UserRepository
from app.registry.constants import SubscriptionPlan, validate_resource_name
from app.registry.exceptions import AuthenticationError, ValidationError
from app.registry.security import hash_api_key
from app.registry.settings import settings
from app.services.analytics_service import AnalyticsService
from app.services.crm_service import CrmService
from app.services.email_service import EmailService
from app.services.identity_service import IdentityService

_SESSION_THRESHOLD = timedelta(minutes=30)

_bearer_scheme = HTTPBearer(auto_error=False)
_api_key_scheme = APIKeyHeader(name="X-API-Key", scheme_name="ApiKey", auto_error=False)
_project_id_scheme = APIKeyHeader(name="X-Project-ID", scheme_name="ProjectID", auto_error=False)
_project_name_scheme = APIKeyHeader(name="X-Project-Name", scheme_name="ProjectName", auto_error=False)
_org_id_scheme = APIKeyHeader(name="X-Organization-ID", scheme_name="OrganizationID", auto_error=False)


async def get_api_context(
    request: Request,
    bearer: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    _org_id: str | None = Depends(_org_id_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> ApiContext:
    """Dependency for management routes — Bearer JWT only.

    Resolves user and organization from the external IdP token.
    """
    request_id: str = getattr(request.state, "request_id", "unknown")

    if not bearer:
        if not settings.AUTH_ENABLED:
            bearer_token = "dev-no-auth"
        else:
            raise AuthenticationError("Bearer token required. Provide Authorization: Bearer <token>.")
    else:
        bearer_token = bearer.credentials

    ctx = await _resolve_jwt(bearer_token, request, session, request_id)
    request.state.api_context = ctx
    return ctx


async def get_data_plane_context(
    request: Request,
    bearer: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    _org_id: str | None = Depends(_org_id_scheme),
    x_api_key: str | None = Depends(_api_key_scheme),
    x_project_id: str | None = Depends(_project_id_scheme),
    x_project_name: str | None = Depends(_project_name_scheme),
    session: AsyncSession = Depends(get_db_session),
) -> ApiContext:
    """Dependency for data-plane routes — Bearer JWT **or** API key.

    When both are present, **API key wins**.  This avoids failures when
    a client (or Swagger UI) sends a stale JWT alongside a valid key.

    **Bearer JWT**: also provide ``X-Project-ID`` to scope the request.

    **API key**: provide ``X-Project-Name`` to select (or auto-create)
    the target project by human-readable name.
    """
    request_id: str = getattr(request.state, "request_id", "unknown")

    if bearer and not x_api_key:
        ctx = await _resolve_jwt(
            bearer.credentials,
            request,
            session,
            request_id,
            project_id_raw=x_project_id,
        )
    elif x_api_key:
        ctx = await _resolve_api_key(
            x_api_key,
            session,
            request_id,
            project_name=x_project_name,
        )
    else:
        if not settings.AUTH_ENABLED:
            ctx = await _resolve_jwt("dev-no-auth", request, session, request_id, project_id_raw=x_project_id)
        else:
            raise AuthenticationError(
                "Missing credentials. Provide Authorization: Bearer <token> (with X-Project-ID) or X-API-Key header."
            )

    request.state.api_context = ctx
    return ctx


def require_project(ctx: ApiContext = Depends(get_data_plane_context)) -> ApiContext:
    """Thin wrapper that guarantees ``ctx.project`` is present."""
    if ctx.project is None:
        raise ValidationError("Project scope required. Provide X-Project-ID (Bearer) or X-Project-Name (API key).")
    return ctx


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _resolve_jwt(
    token: str,
    request: Request,
    session: AsyncSession,
    request_id: str,
    *,
    project_id_raw: str | None = None,
) -> ApiContext:
    """Verify the external IdP JWT, JIT-provision user/org, and optionally resolve a project."""
    adapter = get_auth_adapter()
    claims = await asyncio.to_thread(adapter.verify_token, token)

    user_repo = UserRepository(session)
    identity_repo = IdentityRepository(session)

    user, user_created, prev_sign_in = await user_repo.upsert_user(
        external_id=claims.sub,
        email=claims.email,
        display_name=claims.display_name,
    )

    memberships = await identity_repo.list_user_orgs(user.id)

    if not memberships:
        svc = IdentityService(session)
        await svc.create_organization(
            name="My Organization",
            owner_id=user.id,
            plan=SubscriptionPlan.DEVELOPMENT if not settings.AUTH_ENABLED else None,
        )

        memberships = await identity_repo.list_user_orgs(user.id)

    is_new_user = user_created

    org_id_header = request.headers.get("X-Organization-ID")
    if org_id_header:
        try:
            target_org_id = UUID(org_id_header)
        except ValueError:
            raise ValidationError("X-Organization-ID must be a valid UUID.")

        matched = next((m for m in memberships if m.org_id == target_org_id), None)
        if matched is None:
            raise AuthenticationError("You are not a member of the specified organization.")
        organization = await identity_repo.get_organization(target_org_id)
    else:
        organization = await identity_repo.get_organization(memberships[0].org_id)

    if organization is None:
        raise AuthenticationError("Organization could not be resolved.")

    project = None
    if project_id_raw:
        try:
            project_id = UUID(project_id_raw)
        except ValueError:
            raise ValidationError("X-Project-ID must be a valid UUID.")
        project_repo = ProjectRepository(session)
        project = await project_repo.get_project(project_id)
        if project is None or project.org_id != organization.id:
            raise ValidationError("Project not found or does not belong to your organization.")

    log = structlog.get_logger().bind(
        request_id=request_id,
        org_id=str(organization.id),
        **({"project_id": str(project.id)} if project else {}),
    )

    analytics = AnalyticsService()

    if is_new_user:
        from app.infrastructure.queue.tasks import (
            send_followup_email_task,
            send_welcome_email_task,
            sync_new_user_to_crm,
        )

        if EmailService.is_configured():
            send_welcome_email_task.delay(user.email)
            send_followup_email_task.delay(user.email)

        if CrmService.is_configured():
            sync_new_user_to_crm.delay(user.email)

        analytics.user_signed_up(
            org_id=str(organization.id),
            user_id=str(user.id),
            email=user.email,
        )

        analytics.organization_created(
            org_id=str(organization.id),
            user_id=str(user.id),
            source="signup",
        )

        analytics.identify_org(
            org_id=str(organization.id),
            created_at=organization.created_at,
            owner_user_id=str(user.id),
            owner_email=user.email,
            owner_display_name=user.display_name,
        )

    now = datetime.now(timezone.utc)
    if prev_sign_in is None or (now - prev_sign_in) > _SESSION_THRESHOLD:
        analytics.user_authenticated(
            org_id=str(organization.id),
            user_id=str(user.id),
        )

    return ApiContext(
        request_id=request_id,
        auth_method=AuthMethod.JWT,
        organization=organization,
        project=project,
        user=user,
        logger=log,
    )


async def _resolve_api_key(
    raw_key: str,
    session: AsyncSession,
    request_id: str,
    *,
    project_name: str | None = None,
) -> ApiContext:
    """Validate an API key and resolve the associated org and project.

    The caller supplies ``project_name`` via the ``X-Project-Name``
    header.  The project is resolved by name within the org and
    auto-created if it doesn't exist.
    """
    key_hash = hash_api_key(raw_key)
    identity_repo = IdentityRepository(session)
    project_repo = ProjectRepository(session)

    api_key = await identity_repo.get_api_key_by_hash(key_hash)
    if api_key is None:
        raise AuthenticationError("Invalid or revoked API key.")

    if api_key.expires_at is not None and api_key.expires_at < datetime.now(timezone.utc):
        raise AuthenticationError("API key has expired. Please generate a new one.")

    await identity_repo.touch_api_key(api_key.id)

    organization = await identity_repo.get_organization(api_key.org_id)
    if organization is None:
        raise AuthenticationError("Organization associated with API key not found.")

    project = None
    if project_name and project_name.strip():
        try:
            clean_name = validate_resource_name(project_name, "X-Project-Name")
        except ValueError as exc:
            raise ValidationError(str(exc))
        project = await project_repo.get_or_create_project(
            org_id=api_key.org_id,
            name=clean_name,
        )

    log = structlog.get_logger().bind(
        request_id=request_id,
        org_id=str(organization.id),
        **({"project_id": str(project.id)} if project else {}),
    )

    return ApiContext(
        request_id=request_id,
        auth_method=AuthMethod.API_KEY,
        organization=organization,
        project=project,
        user=None,
        logger=log,
    )
