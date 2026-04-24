"""Routes for the authenticated user's profile and invitations.

All endpoints require a valid external IdP JWT via the
``Authorization: Bearer`` header.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.context import ApiContext
from app.api.dependencies import get_api_context
from app.infrastructure.db.engine import get_db_session
from app.registry.constants import InvitationStatus, MembershipRole
from app.registry.exceptions import AuthenticationError
from app.services.identity_service import IdentityService

router = APIRouter(prefix="/me", tags=["me"])


def _require_user(ctx: ApiContext) -> None:
    if ctx.user is None:
        raise AuthenticationError("This endpoint requires user authentication (Bearer token).")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class UserProfileResponse(BaseModel):
    """Current authenticated user profile."""

    id: UUID
    email: str
    display_name: str
    created_at: str
    last_sign_in_at: str | None


class InvitationResponse(BaseModel):
    """Invitation details returned to the invitee."""

    id: UUID
    org_id: UUID
    org_name: str
    email: str
    role: MembershipRole
    status: InvitationStatus
    invited_by: UUID
    inviter_display_name: str
    inviter_email: str
    created_at: str
    expires_at: str


class MembershipResponse(BaseModel):
    """Membership created after accepting an invitation."""

    id: UUID
    user_id: UUID
    org_id: UUID
    role: MembershipRole
    display_name: str
    email: str
    created_at: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=UserProfileResponse)
async def get_me(
    ctx: ApiContext = Depends(get_api_context),
) -> UserProfileResponse:
    """Return the profile of the currently authenticated user.

    Auth: `Bearer`
    """
    _require_user(ctx)
    return UserProfileResponse(
        id=ctx.user.id,
        email=ctx.user.email,
        display_name=ctx.user.display_name,
        created_at=ctx.user.created_at.isoformat(),
        last_sign_in_at=ctx.user.last_sign_in_at.isoformat() if ctx.user.last_sign_in_at else None,
    )


@router.get("/invitations", response_model=list[InvitationResponse])
async def list_my_invitations(
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> list[InvitationResponse]:
    """List all pending invitations for the current user.

    Auth: `Bearer`
    """
    _require_user(ctx)
    svc = IdentityService(session)
    invitations = await svc.list_my_invitations(ctx.user.email)
    return [
        InvitationResponse(
            id=inv.id,
            org_id=inv.org_id,
            org_name=inv.org_name,
            email=inv.email,
            role=inv.role,
            status=inv.status,
            invited_by=inv.invited_by,
            inviter_display_name=inv.inviter_display_name,
            inviter_email=inv.inviter_email,
            created_at=inv.created_at.isoformat(),
            expires_at=inv.expires_at.isoformat(),
        )
        for inv in invitations
    ]


@router.post("/invitations/{invitation_id}/accept", status_code=200, response_model=MembershipResponse)
async def accept_invitation(
    invitation_id: UUID,
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> MembershipResponse:
    """Accept a pending invitation, joining the organization.

    Auth: `Bearer`
    """
    _require_user(ctx)
    svc = IdentityService(session)
    m = await svc.accept_invitation(user_id=ctx.user.id, invitation_id=invitation_id)
    return MembershipResponse(
        id=m.id,
        user_id=m.user_id,
        org_id=m.org_id,
        role=m.role,
        display_name=m.display_name,
        email=m.email,
        created_at=m.created_at.isoformat(),
    )


@router.post("/invitations/{invitation_id}/decline", status_code=204)
async def decline_invitation(
    invitation_id: UUID,
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Decline a pending invitation.

    Auth: `Bearer`
    """
    _require_user(ctx)
    svc = IdentityService(session)
    await svc.decline_invitation(user_id=ctx.user.id, invitation_id=invitation_id)
