"""Routes for authentication and session management.

``POST /auth/login`` accepts an external identity provider token,
validates it, upserts the user, and returns a short-lived app JWT.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.core.identity.entities import User
from app.infrastructure.auth.jwt import get_auth_adapter
from app.infrastructure.db.engine import get_db_session
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    """Payload for the login endpoint."""

    token: str = Field(description="Access token from the external identity provider (Supabase / Firebase)")


class LoginResponse(BaseModel):
    """Returned after successful login."""

    user_id: UUID
    email: str
    display_name: str
    app_token: str = Field(description="Short-lived Opentracer session JWT")


class MeResponse(BaseModel):
    """Current authenticated user profile."""

    id: UUID
    email: str
    display_name: str
    avatar_url: str
    created_at: str
    last_sign_in_at: str | None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> LoginResponse:
    """Exchange an external IdP token for an Opentracer session JWT.

    The external token is validated by the configured auth adapter
    (Supabase or Firebase).  The user is created on first login.
    """
    adapter = get_auth_adapter()
    svc = AuthService(session, adapter)
    user, app_token = await svc.login(body.token)
    return LoginResponse(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        app_token=app_token,
    )


@router.get("/me", response_model=MeResponse)
async def get_me(
    user: User = Depends(get_current_user),
) -> MeResponse:
    """Return the profile of the currently authenticated user."""
    return MeResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        created_at=user.created_at.isoformat(),
        last_sign_in_at=user.last_sign_in_at.isoformat() if user.last_sign_in_at else None,
    )
