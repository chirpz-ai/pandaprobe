"""Routes for the authenticated user's profile.

All endpoints require a valid external IdP JWT via the
``Authorization: Bearer`` header.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.context import ApiContext
from app.api.dependencies import get_api_context
from app.registry.exceptions import AuthenticationError

router = APIRouter(prefix="/user", tags=["user"])


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
