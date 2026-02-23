"""Routes for managing API keys.

API keys are the primary authentication method for the data-plane
(trace ingestion and evaluation triggers).  Keys are scoped to an
**organization**; the SDK specifies the target project at runtime
via the ``X-Project-Name`` header.

All endpoints require a valid external IdP JWT via the
``Authorization: Bearer`` header.
"""

from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.context import ApiContext
from app.api.dependencies import get_api_context
from app.core.identity.entities import APIKey
from app.infrastructure.db.engine import get_db_session
from app.registry.exceptions import AuthenticationError
from app.services.identity_service import IdentityService

router = APIRouter(tags=["api-keys"])


def _require_user(ctx: ApiContext) -> None:
    if ctx.user is None:
        raise AuthenticationError("This endpoint requires user authentication (Bearer token).")


def _is_effectively_active(key: APIKey) -> bool:
    """True when the key is not revoked AND not expired."""
    if not key.is_active:
        return False
    if key.expires_at is not None and key.expires_at < datetime.now(timezone.utc):
        return False
    return True


def _key_response(key: APIKey, *, raw_key: str | None = None) -> "APIKeyResponse":
    return APIKeyResponse(
        id=key.id,
        org_id=key.org_id,
        key_prefix=key.key_prefix,
        name=key.name,
        is_active=_is_effectively_active(key),
        created_at=key.created_at.isoformat(),
        expires_at=key.expires_at.isoformat() if key.expires_at else None,
        raw_key=raw_key,
    )


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class KeyExpiration(StrEnum):
    """Supported API key lifetime options."""

    NEVER = "never"
    NINETY_DAYS = "90d"


class CreateAPIKeyRequest(BaseModel):
    """Payload for generating a new API key."""

    name: str = Field(min_length=1, max_length=255, description="Human-readable label for the key")
    expiration: KeyExpiration = Field(
        default=KeyExpiration.NEVER,
        description="Key lifetime: 'never' (default, for production) or '90d' (for development)",
    )


class APIKeyResponse(BaseModel):
    """Returned after creating an API key — includes the raw key once."""

    id: UUID
    org_id: UUID
    key_prefix: str
    name: str
    is_active: bool = Field(description="False if the key has been revoked or has expired.")
    created_at: str
    expires_at: str | None
    raw_key: str | None = Field(default=None, description="Shown only at creation time.")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/organizations/{org_id}/api-keys",
    status_code=201,
    response_model=APIKeyResponse,
)
async def create_api_key(
    org_id: UUID,
    body: CreateAPIKeyRequest,
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> APIKeyResponse:
    """Generate a new org-scoped API key. The raw key is shown **only once**.

    Auth: `Bearer`

    The key is org-scoped — the SDK specifies the target project at
    runtime via `X-Project-Name` header.
    Projects are auto-created on first use.

    Expiration: `never` (default, production) · `90d` (90-day TTL, development)
    """
    _require_user(ctx)
    svc = IdentityService(session)
    await svc.require_membership(ctx.user.id, org_id)
    api_key, raw_key = await svc.create_api_key(
        org_id=org_id,
        name=body.name,
        created_by=ctx.user.id,
        expiration=body.expiration.value,
    )
    return _key_response(api_key, raw_key=raw_key)


@router.get(
    "/organizations/{org_id}/api-keys",
    response_model=list[APIKeyResponse],
)
async def list_org_api_keys(
    org_id: UUID,
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[APIKeyResponse]:
    """List all API keys in the organization.

    Auth: `Bearer` · role: any member
    """
    _require_user(ctx)
    svc = IdentityService(session)
    await svc.require_membership(ctx.user.id, org_id)
    keys = await svc.list_api_keys(org_id)
    return [_key_response(k) for k in keys]


@router.get(
    "/organizations/{org_id}/api-keys/{key_id}",
    response_model=APIKeyResponse,
)
async def get_api_key(
    org_id: UUID,
    key_id: UUID,
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> APIKeyResponse:
    """Retrieve a single API key.

    Auth: `Bearer` · role: any member
    """
    _require_user(ctx)
    svc = IdentityService(session)
    await svc.require_membership(ctx.user.id, org_id)
    key = await svc.get_api_key(key_id, org_id=org_id)
    return _key_response(key)


@router.post(
    "/organizations/{org_id}/api-keys/{key_id}/rotate",
    status_code=201,
    response_model=APIKeyResponse,
)
async def rotate_api_key(
    org_id: UUID,
    key_id: UUID,
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> APIKeyResponse:
    """Create a replacement key with a fresh 90-day expiration.

    Auth: `Bearer` · role: `ADMIN` or `OWNER`

    The old key remains active until its original expiration date.
    Only keys with an expiration (e.g. `90d`) can be rotated.
    Production keys (`never`) should be revoked and re-created instead.
    """
    _require_user(ctx)
    svc = IdentityService(session)
    await svc.require_admin(ctx.user.id, org_id)
    new_key, raw_key = await svc.rotate_api_key(
        key_id, org_id=org_id, created_by=ctx.user.id,
    )
    return _key_response(new_key, raw_key=raw_key)


@router.delete("/organizations/{org_id}/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    org_id: UUID,
    key_id: UUID,
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Revoke (soft-delete) an API key.

    Auth: `Bearer` · role: `ADMIN` or `OWNER`
    """
    _require_user(ctx)
    svc = IdentityService(session)
    await svc.require_admin(ctx.user.id, org_id)
    await svc.revoke_api_key(key_id=key_id, org_id=org_id)
