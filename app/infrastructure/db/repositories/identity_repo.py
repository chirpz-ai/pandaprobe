"""PostgreSQL implementation of the Identity repository.

All database access for organizations, memberships, and API keys
flows through this class.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import delete, inspect as sa_inspect, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.identity.entities import APIKey, Membership, Organization
from app.infrastructure.db.models import APIKeyModel, MembershipModel, OrganizationModel, UserModel
from app.registry.constants import MembershipRole


class IdentityRepository:
    """Concrete identity repository backed by PostgreSQL + SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialise with an async database session."""
        self._session = session

    # -- organization ---------------------------------------------------------

    async def create_organization(self, name: str) -> Organization:
        """Insert a new organization row and return the domain entity."""
        row = OrganizationModel(name=name)
        self._session.add(row)
        await self._session.flush()
        return self._to_org(row)

    async def get_organization(self, org_id: UUID) -> Organization | None:
        """Fetch an organization by primary key."""
        row = await self._session.get(OrganizationModel, org_id)
        return self._to_org(row) if row else None

    async def update_organization(self, org_id: UUID, *, name: str | None = None) -> Organization | None:
        """Update mutable organization fields."""
        row = await self._session.get(OrganizationModel, org_id)
        if row is None:
            return None
        if name is not None:
            row.name = name
        await self._session.flush()
        return self._to_org(row)

    async def delete_organization(self, org_id: UUID) -> None:
        """Hard-delete an organization (CASCADE removes related records)."""
        row = await self._session.get(OrganizationModel, org_id)
        if row:
            await self._session.delete(row)
            await self._session.flush()

    # -- Memberships ----------------------------------------------------------

    async def create_membership(
        self,
        user_id: UUID,
        org_id: UUID,
        role: MembershipRole = MembershipRole.MEMBER,
    ) -> Membership:
        """Add a user to an organization with the given role."""
        row = MembershipModel(user_id=user_id, org_id=org_id, role=role.value)
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row, ["user"])
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
        """Return all memberships for an organization with user display info."""
        stmt = (
            select(MembershipModel)
            .options(joinedload(MembershipModel.user))
            .where(MembershipModel.org_id == org_id)
            .order_by(MembershipModel.created_at)
        )
        rows = (await self._session.execute(stmt)).unique().scalars().all()
        return [self._to_membership(r) for r in rows]

    async def update_membership_role(self, user_id: UUID, org_id: UUID, role: MembershipRole) -> Membership | None:
        """Change a member's role and return the updated membership."""
        stmt = (
            select(MembershipModel)
            .options(joinedload(MembershipModel.user))
            .where(MembershipModel.user_id == user_id, MembershipModel.org_id == org_id)
        )
        row = (await self._session.execute(stmt)).unique().scalar_one_or_none()
        if row is None:
            return None
        row.role = role.value
        await self._session.flush()
        return self._to_membership(row)

    async def delete_membership(self, user_id: UUID, org_id: UUID) -> None:
        """Remove a user from an organization."""
        stmt = delete(MembershipModel).where(
            MembershipModel.user_id == user_id,
            MembershipModel.org_id == org_id,
        )
        await self._session.execute(stmt)

    # -- API Keys -------------------------------------------------------------

    async def create_api_key(
        self,
        org_id: UUID,
        project_id: UUID,
        key_hash: str,
        key_prefix: str,
        name: str,
        created_by: UUID | None = None,
        expires_at: datetime | None = None,
    ) -> APIKey:
        """Persist a new API key record and return the domain entity."""
        row = APIKeyModel(
            org_id=org_id,
            project_id=project_id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            name=name,
            created_by=created_by,
            expires_at=expires_at,
        )
        self._session.add(row)
        await self._session.flush()
        return self._to_key(row)

    async def get_api_key(self, key_id: UUID) -> APIKey | None:
        """Look up an API key by primary key."""
        row = await self._session.get(APIKeyModel, key_id)
        return self._to_key(row) if row else None

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
        """Return every API key for an organization (active and revoked)."""
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
        return Organization(id=row.id, name=row.name, created_at=row.created_at)

    @staticmethod
    def _to_membership(row: MembershipModel) -> Membership:
        user: UserModel | None = None
        if "user" not in sa_inspect(row).unloaded:
            user = row.user
        return Membership(
            id=row.id,
            user_id=row.user_id,
            org_id=row.org_id,
            role=MembershipRole(row.role),
            created_at=row.created_at,
            display_name=user.display_name if user else "",
            email=user.email if user else "",
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
            expires_at=row.expires_at,
            last_used_at=row.last_used_at,
            created_by=row.created_by,
        )
