"""Orchestration logic for authentication and user provisioning.

Validates external IdP tokens, upserts local user records, and
issues short-lived app JWTs for session management.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity.entities import User
from app.infrastructure.auth.base import AuthAdapter
from app.infrastructure.auth.jwt import issue_app_token
from app.infrastructure.db.repositories.user_repo import UserRepository


class AuthService:
    """Application service for login and user sync."""

    def __init__(self, session: AsyncSession, adapter: AuthAdapter) -> None:
        """Initialise with a DB session and the active auth adapter."""
        self._user_repo = UserRepository(session)
        self._adapter = adapter

    async def login(self, external_token: str) -> tuple[User, str]:
        """Validate an external JWT, upsert the user, and issue an app token.

        Returns:
            A tuple of (User entity, app_jwt_string).
        """
        claims = await self._adapter.verify_token(external_token)

        user = await self._user_repo.upsert_user(
            user_id=UUID(claims.sub),
            email=claims.email,
            display_name=claims.display_name,
        )

        app_token = issue_app_token(user.id, user.email)
        return user, app_token
