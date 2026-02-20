"""Routes for managing organizations and memberships.

All endpoints require a valid external IdP JWT via the
``Authorization: Bearer`` header.  Organization mutations are
restricted to admins/owners.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.context import ApiContext
from app.api.dependencies import get_api_context
from app.infrastructure.db.engine import get_db_session
from app.registry.constants import MembershipRole
from app.registry.exceptions import AuthenticationError
from app.services.identity_service import IdentityService

router = APIRouter(prefix="/organizations", tags=["organizations"])


def _require_user(ctx: ApiContext) -> None:
    if ctx.user is None:
        raise AuthenticationError("This endpoint requires user authentication (Bearer token).")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class CreateOrganizationRequest(BaseModel):
    """Payload for creating a new organization."""

    name: str = Field(min_length=1, max_length=255)


class OrganizationResponse(BaseModel):
    """Public representation of an organization."""

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


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", status_code=201, response_model=OrganizationResponse)
async def create_organization(
    body: CreateOrganizationRequest,
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> OrganizationResponse:
    """Register a new organization. The caller becomes the OWNER.

    Auth: `Bearer`
    """
    _require_user(ctx)
    svc = IdentityService(session)
    org = await svc.create_organization(name=body.name, owner_id=ctx.user.id)
    return OrganizationResponse(id=org.id, name=org.name, slug=org.slug, created_at=org.created_at.isoformat())


@router.get("", response_model=list[OrganizationResponse])
async def list_my_organizations(
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[OrganizationResponse]:
    """List organizations the current user belongs to.

    Auth: `Bearer`
    """
    _require_user(ctx)
    svc = IdentityService(session)
    memberships = await svc.list_user_orgs(ctx.user.id)
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
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[MembershipResponse]:
    """List all members of an organization.

    Auth: `Bearer`
    """
    _require_user(ctx)
    svc = IdentityService(session)
    await svc.require_membership(ctx.user.id, org_id)
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
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> MembershipResponse:
    """Invite a user to an organization.

    Auth: `Bearer` · role: `ADMIN` or `OWNER`
    """
    _require_user(ctx)
    svc = IdentityService(session)
    await svc.require_admin(ctx.user.id, org_id)
    m = await svc.add_member(org_id, body.user_id, body.role)
    return MembershipResponse(
        id=m.id, user_id=m.user_id, org_id=m.org_id, role=m.role, created_at=m.created_at.isoformat()
    )
