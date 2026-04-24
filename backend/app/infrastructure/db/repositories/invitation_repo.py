"""PostgreSQL repository for organization invitations."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, inspect as sa_inspect, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.identity.entities import Invitation
from app.infrastructure.db.models import InvitationModel, OrganizationModel, UserModel
from app.registry.constants import InvitationStatus, MembershipRole


class InvitationRepository:
    """Handles invitation persistence and lookups."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_invitation(
        self,
        org_id: UUID,
        email: str,
        role: MembershipRole,
        invited_by: UUID,
        expires_at: datetime,
    ) -> Invitation:
        """Persist a new invitation and return the domain entity."""
        row = InvitationModel(
            org_id=org_id,
            email=email,
            role=role.value,
            invited_by=invited_by,
            expires_at=expires_at,
        )
        self._session.add(row)
        await self._session.flush()
        await self._session.refresh(row, ["organization", "inviter"])
        return self._to_entity(row)

    async def get_invitation(self, invitation_id: UUID) -> Invitation | None:
        """Fetch a single invitation by ID, or None."""
        stmt = (
            select(InvitationModel)
            .options(joinedload(InvitationModel.organization), joinedload(InvitationModel.inviter))
            .where(InvitationModel.id == invitation_id)
        )
        row = (await self._session.execute(stmt)).unique().scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def get_pending_invitation(self, org_id: UUID, email: str) -> Invitation | None:
        """Find an existing PENDING invitation for the given org + email pair."""
        stmt = (
            select(InvitationModel)
            .options(joinedload(InvitationModel.organization), joinedload(InvitationModel.inviter))
            .where(
                InvitationModel.org_id == org_id,
                InvitationModel.email == email,
                InvitationModel.status == InvitationStatus.PENDING,
            )
        )
        row = (await self._session.execute(stmt)).unique().scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def list_org_invitations(self, org_id: UUID, status: InvitationStatus | None = None) -> list[Invitation]:
        """Return all invitations for an org, optionally filtered by status."""
        stmt = (
            select(InvitationModel)
            .options(joinedload(InvitationModel.organization), joinedload(InvitationModel.inviter))
            .where(InvitationModel.org_id == org_id)
        )
        if status is not None:
            stmt = stmt.where(InvitationModel.status == status)
        stmt = stmt.order_by(InvitationModel.created_at.desc())
        rows = (await self._session.execute(stmt)).unique().scalars().all()
        return [self._to_entity(r) for r in rows]

    async def list_pending_for_email(self, email: str) -> list[Invitation]:
        """Return all non-expired PENDING invitations addressed to *email*."""
        now = datetime.now(timezone.utc)
        stmt = (
            select(InvitationModel)
            .options(joinedload(InvitationModel.organization), joinedload(InvitationModel.inviter))
            .where(
                InvitationModel.email == email,
                InvitationModel.status == InvitationStatus.PENDING,
                InvitationModel.expires_at > now,
            )
            .order_by(InvitationModel.created_at.desc())
        )
        rows = (await self._session.execute(stmt)).unique().scalars().all()
        return [self._to_entity(r) for r in rows]

    async def update_status(self, invitation_id: UUID, new_status: InvitationStatus) -> Invitation | None:
        """Transition an invitation to a new status."""
        stmt = (
            select(InvitationModel)
            .options(joinedload(InvitationModel.organization), joinedload(InvitationModel.inviter))
            .where(InvitationModel.id == invitation_id)
        )
        row = (await self._session.execute(stmt)).unique().scalar_one_or_none()
        if row is None:
            return None
        row.status = new_status.value
        await self._session.flush()
        return self._to_entity(row)

    async def count_pending_for_org(self, org_id: UUID) -> int:
        """Count PENDING invitations for quota enforcement."""
        stmt = select(func.count()).select_from(InvitationModel).where(
            InvitationModel.org_id == org_id,
            InvitationModel.status == InvitationStatus.PENDING,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    @staticmethod
    def _to_entity(row: InvitationModel) -> Invitation:
        org: OrganizationModel | None = None
        if "organization" not in sa_inspect(row).unloaded:
            org = row.organization
        inviter: UserModel | None = None
        if "inviter" not in sa_inspect(row).unloaded:
            inviter = row.inviter
        return Invitation(
            id=row.id,
            org_id=row.org_id,
            email=row.email,
            role=MembershipRole(row.role),
            invited_by=row.invited_by,
            status=InvitationStatus(row.status),
            created_at=row.created_at,
            expires_at=row.expires_at,
            org_name=org.name if org else "",
            inviter_display_name=inviter.display_name if inviter else "",
            inviter_email=inviter.email if inviter else "",
        )
