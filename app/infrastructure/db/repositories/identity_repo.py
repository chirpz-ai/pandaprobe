"""PostgreSQL implementation of the Identity repository.

All database access for organisations, memberships, and API keys
flows through this class.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.identity.entities import APIKey, Membership, Organization
from app.infrastructure.db.models import APIKeyModel, MembershipModel, OrganizationModel
from app.registry.constants import MembershipRole


class IdentityRepository:
    """Concrete identity repository backed by PostgreSQL + SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an async database session."""
        self._session = session

    # -- Organisation ---------------------------------------------------------

    async def create_organization(self, name: str, slug: str) -> Organization:
        """Insert a new organisation row and return the domain entity."""
        row = OrganizationModel(name=name, slug=slug)
        self._session.add(row)
        await self._session.flush()
        return self._to_org(row)

    async def get_organization(self, org_id: UUID) -> Organization | None:
        """Fetch an organisation by primary key."""
        row = await self._session.get(OrganizationModel, org_id)
        return self._to_org(row) if row else None

    async def get_organization_by_slug(self, slug: str) -> Organization | None:
        """Fetch an organisation by unique slug."""
        stmt = select(OrganizationModel).where(OrganizationModel.slug == slug)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_org(row) if row else None

    # -- Memberships ----------------------------------------------------------

    async def create_membership(
        self,
        user_id: UUID,
        org_id: UUID,
        role: MembershipRole = MembershipRole.MEMBER,
    ) -> Membership:
        """Add a user to an organisation with the given role."""
        row = MembershipModel(user_id=user_id, org_id=org_id, role=role.value)
        self._session.add(row)
        await self._session.flush()
        return self._to_membership(row)

    async def get_membership(self, user_id: UUID, org_id: UUID) -> Membership | None:
        """Look up a specific user-org membership."""
        stmt = select(MembershipModel).where(
            MembershipModel.user_id == user_id,
            MembershipModel.org_id == org_id,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_membership(row) if row else None

    async def list_user_orgs(self, user_id: UUID) -> list[Membership]:
        """Return all memberships for a user."""
        stmt = (
            select(MembershipModel)
            .where(MembershipModel.user_id == user_id)
            .order_by(MembershipModel.created_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_membership(r) for r in rows]

    async def list_org_members(self, org_id: UUID) -> list[Membership]:
        """Return all memberships for an organisation."""
        stmt = select(MembershipModel).where(MembershipModel.org_id == org_id).order_by(MembershipModel.created_at)
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_membership(r) for r in rows]

    # -- API Keys -------------------------------------------------------------

    async def create_api_key(
        self,
        org_id: UUID,
        project_id: UUID,
        key_hash: str,
        key_prefix: str,
        name: str,
        created_by: UUID | None = None,
    ) -> APIKey:
        """Persist a new API key record and return the domain entity."""
        row = APIKeyModel(
            org_id=org_id,
            project_id=project_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=name,
            created_by=created_by,
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
        stmt = update(APIKeyModel).where(APIKeyModel.id == key_id).values(last_used_at=datetime.now(timezone.utc))
        await self._session.execute(stmt)

    async def revoke_api_key(self, key_id: UUID) -> None:
        """Soft-delete by setting ``is_active = False``."""
        stmt = update(APIKeyModel).where(APIKeyModel.id == key_id).values(is_active=False)
        await self._session.execute(stmt)

    async def list_api_keys(self, org_id: UUID) -> list[APIKey]:
        """Return every API key for an organisation (active and revoked)."""
        stmt = select(APIKeyModel).where(APIKeyModel.org_id == org_id).order_by(APIKeyModel.created_at.desc())
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_key(r) for r in rows]

    async def list_project_api_keys(self, project_id: UUID) -> list[APIKey]:
        """Return every API key for a specific project."""
        stmt = select(APIKeyModel).where(APIKeyModel.project_id == project_id).order_by(APIKeyModel.created_at.desc())
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_key(r) for r in rows]

    # -- Mappers --------------------------------------------------------------

    @staticmethod
    def _to_org(row: OrganizationModel) -> Organization:
        return Organization(id=row.id, name=row.name, slug=row.slug, created_at=row.created_at)

    @staticmethod
    def _to_membership(row: MembershipModel) -> Membership:
        return Membership(
            id=row.id,
            user_id=row.user_id,
            org_id=row.org_id,
            role=MembershipRole(row.role),
            created_at=row.created_at,
        )

    @staticmethod
    def _to_key(row: APIKeyModel) -> APIKey:
        return APIKey(
            id=row.id,
            org_id=row.org_id,
            project_id=row.project_id,
            key_hash=row.key_hash,
            key_prefix=row.key_prefix,
            name=row.name,
            is_active=row.is_active,
            created_at=row.created_at,
            last_used_at=row.last_used_at,
            created_by=row.created_by,
        )
