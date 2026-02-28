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


class UpdateOrganizationRequest(BaseModel):
    """Payload for updating an organization. Only provided fields are changed."""

    name: str | None = Field(default=None, min_length=1, max_length=255)


class OrganizationResponse(BaseModel):
    """Public representation of an organization."""

    id: UUID
    name: str
    created_at: str


class MyOrganizationResponse(OrganizationResponse):
    """Organization with the caller's role included."""

    role: MembershipRole


class MembershipResponse(BaseModel):
    """Membership entry with user display info."""

    id: UUID
    user_id: UUID
    org_id: UUID
    role: MembershipRole
    display_name: str
    email: str
    created_at: str


class AddMemberRequest(BaseModel):
    """Payload for inviting a user to an org."""

    user_id: UUID
    role: MembershipRole = MembershipRole.MEMBER


class UpdateMemberRoleRequest(BaseModel):
    """Payload for changing a member's role."""

    role: MembershipRole


# ---------------------------------------------------------------------------
# Organization CRUD
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
    return OrganizationResponse(id=org.id, name=org.name, created_at=org.created_at.isoformat())


@router.get("", response_model=list[MyOrganizationResponse])
async def list_my_organizations(
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[MyOrganizationResponse]:
    """List organizations the current user belongs to, including their role.

    Auth: `Bearer`
    """
    _require_user(ctx)
    svc = IdentityService(session)
    memberships = await svc.list_user_orgs(ctx.user.id)
    result: list[MyOrganizationResponse] = []
    for m in memberships:
        org = await svc.get_organization(m.org_id)
        result.append(
            MyOrganizationResponse(
                id=org.id,
                name=org.name,
                created_at=org.created_at.isoformat(),
                role=m.role,
            )
        )
    return result


@router.get("/{org_id}", response_model=OrganizationResponse)
async def get_organization(
    org_id: UUID,
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> OrganizationResponse:
    """Get details of a specific organization.

    Auth: `Bearer` · role: any member
    """
    _require_user(ctx)
    svc = IdentityService(session)
    await svc.require_membership(ctx.user.id, org_id)
    org = await svc.get_organization(org_id)
    return OrganizationResponse(id=org.id, name=org.name, created_at=org.created_at.isoformat())


@router.patch("/{org_id}", response_model=OrganizationResponse)
async def update_organization(
    org_id: UUID,
    body: UpdateOrganizationRequest,
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> OrganizationResponse:
    """Update an organization. Only provided fields are changed.

    Auth: `Bearer` · role: `ADMIN` or `OWNER`
    """
    _require_user(ctx)
    svc = IdentityService(session)
    await svc.require_admin(ctx.user.id, org_id)
    org = await svc.update_organization(org_id, name=body.name)
    return OrganizationResponse(id=org.id, name=org.name, created_at=org.created_at.isoformat())


@router.delete("/{org_id}", status_code=204)
async def delete_organization(
    org_id: UUID,
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Permanently delete an organization and all related data.

    Auth: `Bearer` · role: `OWNER`
    """
    _require_user(ctx)
    svc = IdentityService(session)
    await svc.require_owner(ctx.user.id, org_id)
    await svc.delete_organization(org_id)


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


@router.get("/{org_id}/members", response_model=list[MembershipResponse])
async def list_members(
    org_id: UUID,
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[MembershipResponse]:
    """List all members of an organization with display info.

    Auth: `Bearer` · role: any member
    """
    _require_user(ctx)
    svc = IdentityService(session)
    await svc.require_membership(ctx.user.id, org_id)
    members = await svc.list_org_members(org_id)
    return [
        MembershipResponse(
            id=m.id,
            user_id=m.user_id,
            org_id=m.org_id,
            role=m.role,
            display_name=m.display_name,
            email=m.email,
            created_at=m.created_at.isoformat(),
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

    Auth: `Bearer` · hierarchy: `OWNER` > `ADMIN` > `MEMBER`

    - **OWNER** can assign any role
    - **ADMIN** can assign MEMBER only
    - **MEMBER** cannot add anyone
    """
    _require_user(ctx)
    svc = IdentityService(session)
    m = await svc.add_member(actor_id=ctx.user.id, org_id=org_id, user_id=body.user_id, role=body.role)
    return MembershipResponse(
        id=m.id,
        user_id=m.user_id,
        org_id=m.org_id,
        role=m.role,
        display_name=m.display_name,
        email=m.email,
        created_at=m.created_at.isoformat(),
    )


@router.patch("/{org_id}/members/{user_id}", response_model=MembershipResponse)
async def update_member_role(
    org_id: UUID,
    user_id: UUID,
    body: UpdateMemberRoleRequest,
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> MembershipResponse:
    """Change a member's role within an organization.

    Auth: `Bearer` · role: `OWNER`

    - **OWNER** can change any non-OWNER to any role
    - Cannot change another OWNER's role
    - Cannot change your own role
    """
    _require_user(ctx)
    svc = IdentityService(session)
    m = await svc.update_member_role(
        actor_id=ctx.user.id,
        org_id=org_id,
        target_user_id=user_id,
        new_role=body.role,
    )
    return MembershipResponse(
        id=m.id,
        user_id=m.user_id,
        org_id=m.org_id,
        role=m.role,
        display_name=m.display_name,
        email=m.email,
        created_at=m.created_at.isoformat(),
    )


@router.delete("/{org_id}/members/{user_id}", status_code=204)
async def remove_member(
    org_id: UUID,
    user_id: UUID,
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Remove a member from an organization.

    Auth: `Bearer` · hierarchy: `OWNER` > `ADMIN` > `MEMBER`

    - **OWNER** can remove ADMINs and MEMBERs
    - **ADMIN** can remove MEMBERs only
    - **MEMBER** cannot remove anyone
    - **OWNER** role cannot be removed
    """
    _require_user(ctx)
    svc = IdentityService(session)
    await svc.remove_member(actor_id=ctx.user.id, org_id=org_id, target_user_id=user_id)
