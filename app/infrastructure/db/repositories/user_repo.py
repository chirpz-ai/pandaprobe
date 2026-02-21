"""PostgreSQL repository for Users."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity.entities import User
from app.infrastructure.db.models import UserModel


class UserRepository:
    """Handles user persistence and lookups."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an async database session."""
        self._session = session

    async def upsert_user(self, external_id: str, email: str, display_name: str = "") -> User:
        """Create a user or update their last sign-in if they already exist.

        Lookup is by ``external_id`` (the IdP's native identifier).
        The internal ``id`` (UUID) is auto-generated for new users.
        """
        stmt = select(UserModel).where(UserModel.external_id == external_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        if row is None:
            row = UserModel(
                external_id=external_id,
                email=email,
                display_name=display_name,
                last_sign_in_at=datetime.now(timezone.utc),
            )
            self._session.add(row)
        else:
            row.last_sign_in_at = datetime.now(timezone.utc)
            if display_name and not row.display_name:
                row.display_name = display_name
        await self._session.flush()
        return self._to_entity(row)

    async def get_user(self, user_id: UUID) -> User | None:
        """Fetch a user by primary key."""
        row = await self._session.get(UserModel, user_id)
        return self._to_entity(row) if row else None

    async def get_user_by_email(self, email: str) -> User | None:
        """Fetch a user by email address."""
        stmt = select(UserModel).where(UserModel.email == email)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_entity(row) if row else None

    @staticmethod
    def _to_entity(row: UserModel) -> User:
        return User(
            id=row.id,
            external_id=row.external_id,
            email=row.email,
            display_name=row.display_name,
            created_at=row.created_at,
            last_sign_in_at=row.last_sign_in_at,
        )
