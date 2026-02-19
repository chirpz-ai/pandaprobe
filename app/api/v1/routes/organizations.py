"""Routes for managing organisations, memberships, and API keys.

All endpoints require a valid app JWT via the ``X-Auth-Token`` header.
Organisation mutations are restricted to admins/owners.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.core.identity.entities import User
from app.infrastructure.db.engine import get_db_session
from app.registry.constants import MembershipRole
from app.services.identity_service import IdentityService

router = APIRouter(prefix="/organizations", tags=["organizations"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CreateOrganizationRequest(BaseModel):
    """Payload for creating a new organisation."""

    name: str = Field(min_length=1, max_length=255)


class OrganizationResponse(BaseModel):
    """Public representation of an organisation."""

    id: UUID
    name: str
    slug: str
    created_at: str


class MembershipResponse(BaseModel):
    """Membership entry."""

    id: UUID
    user_id: UUID
    org_id: UUID
    role: MembershipRole
    created_at: str


class AddMemberRequest(BaseModel):
    """Payload for inviting a user to an org."""

    user_id: UUID
    role: MembershipRole = MembershipRole.MEMBER


class CreateAPIKeyRequest(BaseModel):
    """Payload for generating a new API key (must specify project)."""

    project_id: UUID
    name: str = Field(min_length=1, max_length=255, description="Human-readable label for the key")


class APIKeyResponse(BaseModel):
    """Returned after creating an API key -- includes the raw key once."""

    id: UUID
    org_id: UUID
    project_id: UUID
    key_prefix: str
    name: str
    is_active: bool
    created_at: str
    raw_key: str | None = Field(default=None, description="Shown only at creation time.")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", status_code=201, response_model=OrganizationResponse)
async def create_organization(
    body: CreateOrganizationRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> OrganizationResponse:
    """Register a new organization. The caller becomes the OWNER."""
    svc = IdentityService(session)
    org = await svc.create_organization(name=body.name, owner_id=user.id)
    return OrganizationResponse(id=org.id, name=org.name, slug=org.slug, created_at=org.created_at.isoformat())


@router.get("", response_model=list[OrganizationResponse])
async def list_my_organizations(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[OrganizationResponse]:
    """List organisations the current user belongs to."""
    svc = IdentityService(session)
    memberships = await svc.list_user_orgs(user.id)
    result: list[OrganizationResponse] = []
    for m in memberships:
        org = await svc.get_organization(m.org_id)
        result.append(
            OrganizationResponse(id=org.id, name=org.name, slug=org.slug, created_at=org.created_at.isoformat())
        )
    return result


# -- Members ------------------------------------------------------------------


@router.get("/{org_id}/members", response_model=list[MembershipResponse])
async def list_members(
    org_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[MembershipResponse]:
    """List all members of an organisation."""
    svc = IdentityService(session)
    await svc.require_membership(user.id, org_id)
    members = await svc.list_org_members(org_id)
    return [
        MembershipResponse(
            id=m.id, user_id=m.user_id, org_id=m.org_id, role=m.role, created_at=m.created_at.isoformat()
        )
        for m in members
    ]


@router.post("/{org_id}/members", status_code=201, response_model=MembershipResponse)
async def add_member(
    org_id: UUID,
    body: AddMemberRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> MembershipResponse:
    """Invite a user to an organisation. Requires ADMIN or OWNER role."""
    svc = IdentityService(session)
    await svc.require_admin(user.id, org_id)
    m = await svc.add_member(org_id, body.user_id, body.role)
    return MembershipResponse(
        id=m.id, user_id=m.user_id, org_id=m.org_id, role=m.role, created_at=m.created_at.isoformat()
    )


# -- API Keys -----------------------------------------------------------------


@router.post("/{org_id}/api-keys", status_code=201, response_model=APIKeyResponse)
async def create_api_key(
    org_id: UUID,
    body: CreateAPIKeyRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> APIKeyResponse:
    """Generate a new API key scoped to a project within the org.

    The raw key value is returned **only once** in the response body.
    """
    svc = IdentityService(session)
    await svc.require_membership(user.id, org_id)
    api_key, raw_key = await svc.create_api_key(
        org_id=org_id,
        project_id=body.project_id,
        name=body.name,
        created_by=user.id,
    )
    return APIKeyResponse(
        id=api_key.id,
        org_id=api_key.org_id,
        project_id=api_key.project_id,
        key_prefix=api_key.key_prefix,
        name=api_key.name,
        is_active=api_key.is_active,
        created_at=api_key.created_at.isoformat(),
        raw_key=raw_key,
    )


@router.get("/{org_id}/api-keys", response_model=list[APIKeyResponse])
async def list_api_keys(
    org_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[APIKeyResponse]:
    """List all API keys belonging to an organisation."""
    svc = IdentityService(session)
    await svc.require_membership(user.id, org_id)
    keys = await svc.list_api_keys(org_id=org_id)
    return [
        APIKeyResponse(
            id=k.id,
            org_id=k.org_id,
            project_id=k.project_id,
            key_prefix=k.key_prefix,
            name=k.name,
            is_active=k.is_active,
            created_at=k.created_at.isoformat(),
        )
        for k in keys
    ]


@router.delete("/{org_id}/api-keys/{key_id}", status_code=204)
async def revoke_api_key(
    org_id: UUID,
    key_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Revoke (soft-delete) an API key. Requires org membership."""
    svc = IdentityService(session)
    await svc.require_admin(user.id, org_id)
    await svc.revoke_api_key(key_id=key_id, org_id=org_id)
