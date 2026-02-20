"""Routes for user profile retrieval.

The ``/auth/me`` endpoint returns the currently authenticated user's
profile.  Authentication is handled by the unified ``ApiContext``
dependency which validates external IdP JWTs directly.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.context import ApiContext
from app.api.dependencies import get_api_context
from app.registry.exceptions import AuthenticationError

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class MeResponse(BaseModel):
    """Current authenticated user profile."""

    id: UUID
    email: str
    display_name: str
    created_at: str
    last_sign_in_at: str | None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/me", response_model=MeResponse)
async def get_me(
    ctx: ApiContext = Depends(get_api_context),
) -> MeResponse:
    """Return the profile of the currently authenticated user.

    Auth: `Bearer`
    """
    if ctx.user is None:
        raise AuthenticationError("This endpoint requires user authentication (Bearer token).")
    return MeResponse(
        id=ctx.user.id,
        email=ctx.user.email,
        display_name=ctx.user.display_name,
        created_at=ctx.user.created_at.isoformat(),
        last_sign_in_at=ctx.user.last_sign_in_at.isoformat() if ctx.user.last_sign_in_at else None,
    )
