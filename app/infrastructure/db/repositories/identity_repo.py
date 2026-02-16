"""PostgreSQL implementation of the Identity repository.

All database access for organisations and API keys flows through this
class.  It translates between ORM rows and pure domain entities.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity.entities import APIKey, Organization
from app.infrastructure.db.models import APIKeyModel, OrganizationModel


class IdentityRepository:
    """Concrete identity repository backed by PostgreSQL + SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an async database session."""
        self._session = session

    # -- Organisation ---------------------------------------------------------

    async def create_organization(self, name: str) -> Organization:
        """Insert a new organisation row and return the domain entity."""
        row = OrganizationModel(name=name)
        self._session.add(row)
        await self._session.flush()
        return self._to_org(row)

    async def get_organization(self, org_id: UUID) -> Organization | None:
        """Fetch an organisation by primary key."""
        row = await self._session.get(OrganizationModel, org_id)
        return self._to_org(row) if row else None

    # -- API Keys -------------------------------------------------------------

    async def create_api_key(
        self,
        org_id: UUID,
        key_hash: str,
        key_prefix: str,
        name: str,
    ) -> APIKey:
        """Persist a new API key record and return the domain entity."""
        row = APIKeyModel(
            org_id=org_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=name,
        )
        self._session.add(row)
        await self._session.flush()
        return self._to_key(row)

    async def get_api_key_by_hash(self, key_hash: str) -> APIKey | None:
        """Look up an active API key by its SHA-256 hash."""
        stmt = select(APIKeyModel).where(
            APIKeyModel.key_hash == key_hash,
            APIKeyModel.is_active.is_(True),
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_key(row) if row else None

    async def touch_api_key(self, key_id: UUID) -> None:
        """Stamp ``last_used_at`` with the current UTC time."""
        stmt = (
            update(APIKeyModel)
            .where(APIKeyModel.id == key_id)
            .values(last_used_at=datetime.now(timezone.utc))
        )
        await self._session.execute(stmt)

    async def revoke_api_key(self, key_id: UUID) -> None:
        """Soft-delete by setting ``is_active = False``."""
        stmt = (
            update(APIKeyModel)
            .where(APIKeyModel.id == key_id)
            .values(is_active=False)
        )
        await self._session.execute(stmt)

    async def list_api_keys(self, org_id: UUID) -> list[APIKey]:
        """Return every API key for an organisation (active and revoked)."""
        stmt = select(APIKeyModel).where(APIKeyModel.org_id == org_id).order_by(APIKeyModel.created_at.desc())
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_key(r) for r in rows]

    # -- Mappers --------------------------------------------------------------

    @staticmethod
    def _to_org(row: OrganizationModel) -> Organization:
        return Organization(id=row.id, name=row.name, created_at=row.created_at)

    @staticmethod
    def _to_key(row: APIKeyModel) -> APIKey:
        return APIKey(
            id=row.id,
            org_id=row.org_id,
            key_hash=row.key_hash,
            key_prefix=row.key_prefix,
            name=row.name,
            is_active=row.is_active,
            created_at=row.created_at,
            last_used_at=row.last_used_at,
        )
