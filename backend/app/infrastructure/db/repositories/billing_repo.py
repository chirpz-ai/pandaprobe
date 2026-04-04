"""PostgreSQL repository for subscriptions and usage records."""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.billing.entities import Subscription, UsageRecord
from app.infrastructure.db.models import SubscriptionModel, UsageRecordModel
from app.registry.constants import SubscriptionPlan, SubscriptionStatus


class BillingRepository:
    """Concrete billing repository backed by PostgreSQL + SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -- Subscriptions --------------------------------------------------------

    async def create_subscription(
        self,
        org_id: UUID,
        plan: SubscriptionPlan = SubscriptionPlan.HOBBY,
        *,
        stripe_customer_id: str | None = None,
        stripe_subscription_id: str | None = None,
        period_start: datetime | None = None,
        period_end: datetime | None = None,
    ) -> Subscription:
        """Create a new subscription for an organization."""
        now = datetime.now(timezone.utc)
        start = period_start or now
        end = period_end or (now + timedelta(days=30))
        row = SubscriptionModel(
            org_id=org_id,
            plan=plan.value,
            status=SubscriptionStatus.ACTIVE.value,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            current_period_start=start,
            current_period_end=end,
        )
        self._session.add(row)
        await self._session.flush()
        return self._to_subscription(row)

    async def get_subscription_by_org(self, org_id: UUID) -> Subscription | None:
        """Fetch the subscription for an organization."""
        stmt = select(SubscriptionModel).where(SubscriptionModel.org_id == org_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_subscription(row) if row else None

    async def get_subscription_by_stripe_customer(self, stripe_customer_id: str) -> Subscription | None:
        """Look up a subscription by Stripe customer ID."""
        stmt = select(SubscriptionModel).where(SubscriptionModel.stripe_customer_id == stripe_customer_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_subscription(row) if row else None

    async def get_subscription_by_stripe_subscription(self, stripe_subscription_id: str) -> Subscription | None:
        """Look up a subscription by Stripe subscription ID."""
        stmt = select(SubscriptionModel).where(SubscriptionModel.stripe_subscription_id == stripe_subscription_id)
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_subscription(row) if row else None

    async def update_subscription(self, org_id: UUID, **fields: object) -> Subscription | None:
        """Update subscription fields for an organization."""
        row = (
            await self._session.execute(select(SubscriptionModel).where(SubscriptionModel.org_id == org_id))
        ).scalar_one_or_none()
        if row is None:
            return None
        for key, value in fields.items():
            if hasattr(row, key):
                setattr(row, key, value)
        await self._session.flush()
        return self._to_subscription(row)

    async def list_subscriptions_by_plan(
        self, plan: SubscriptionPlan, *, status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    ) -> list[Subscription]:
        """Return all active subscriptions for a given plan."""
        stmt = select(SubscriptionModel).where(
            SubscriptionModel.plan == plan.value,
            SubscriptionModel.status == status.value,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_subscription(r) for r in rows]

    async def list_hobby_subscriptions_due_for_reset(self, now: datetime) -> list[Subscription]:
        """Return HOBBY subscriptions whose period has ended."""
        stmt = select(SubscriptionModel).where(
            SubscriptionModel.plan == SubscriptionPlan.HOBBY.value,
            SubscriptionModel.status == SubscriptionStatus.ACTIVE.value,
            SubscriptionModel.current_period_end <= now,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_subscription(r) for r in rows]

    async def list_paid_subscriptions_active(self) -> list[Subscription]:
        """Return all active paid subscriptions (PRO, STARTUP, ENTERPRISE)."""
        stmt = select(SubscriptionModel).where(
            SubscriptionModel.plan != SubscriptionPlan.HOBBY.value,
            SubscriptionModel.status == SubscriptionStatus.ACTIVE.value,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_subscription(r) for r in rows]

    async def list_all_active_org_ids(self) -> list[UUID]:
        """Return org IDs for all active subscriptions (any plan)."""
        stmt = select(SubscriptionModel.org_id).where(SubscriptionModel.status == SubscriptionStatus.ACTIVE.value)
        rows = (await self._session.execute(stmt)).scalars().all()
        return list(rows)

    async def list_paid_active_org_ids(self) -> list[UUID]:
        """Return org IDs for active paid subscriptions only."""
        stmt = select(SubscriptionModel.org_id).where(
            SubscriptionModel.plan != SubscriptionPlan.HOBBY.value,
            SubscriptionModel.status == SubscriptionStatus.ACTIVE.value,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return list(rows)

    async def list_hobby_org_ids_due_for_reset(self, now: datetime) -> list[UUID]:
        """Return org IDs for HOBBY subscriptions whose period has ended."""
        stmt = select(SubscriptionModel.org_id).where(
            SubscriptionModel.plan == SubscriptionPlan.HOBBY.value,
            SubscriptionModel.status == SubscriptionStatus.ACTIVE.value,
            SubscriptionModel.current_period_end <= now,
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return list(rows)

    async def advance_period(self, org_id: UUID, new_start: datetime, new_end: datetime) -> None:
        """Move a subscription to a new billing period."""
        stmt = (
            update(SubscriptionModel)
            .where(SubscriptionModel.org_id == org_id)
            .values(
                current_period_start=new_start,
                current_period_end=new_end,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await self._session.execute(stmt)

    # -- Usage records --------------------------------------------------------

    async def create_usage_record(
        self,
        org_id: UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> UsageRecord:
        """Create a fresh usage record for a billing period."""
        row = UsageRecordModel(
            org_id=org_id,
            period_start=period_start,
            period_end=period_end,
        )
        self._session.add(row)
        await self._session.flush()
        return self._to_usage(row)

    async def get_current_usage_record(self, org_id: UUID, period_start: datetime) -> UsageRecord | None:
        """Fetch the usage record for the current billing period."""
        stmt = select(UsageRecordModel).where(
            UsageRecordModel.org_id == org_id,
            UsageRecordModel.period_start == period_start,
        )
        row = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_usage(row) if row else None

    async def get_or_create_usage_record(
        self, org_id: UUID, period_start: datetime, period_end: datetime
    ) -> UsageRecord:
        """Get the current usage record or create one if it doesn't exist."""
        existing = await self.get_current_usage_record(org_id, period_start)
        if existing:
            return existing
        return await self.create_usage_record(org_id, period_start, period_end)

    async def get_unbilled_usage_records(self, org_id: UUID) -> list[UsageRecord]:
        """Return all un-billed usage records for an org."""
        stmt = (
            select(UsageRecordModel)
            .where(
                UsageRecordModel.org_id == org_id,
                UsageRecordModel.billed.is_(False),
            )
            .order_by(UsageRecordModel.period_start)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_usage(r) for r in rows]

    async def upsert_usage_counters(
        self,
        org_id: UUID,
        period_start: datetime,
        period_end: datetime,
        *,
        trace_count: int = 0,
        trace_eval_count: int = 0,
        session_eval_count: int = 0,
    ) -> None:
        """Set usage counters from Redis snapshot (absolute values)."""
        row = (
            await self._session.execute(
                select(UsageRecordModel).where(
                    UsageRecordModel.org_id == org_id,
                    UsageRecordModel.period_start == period_start,
                )
            )
        ).scalar_one_or_none()

        if row is None:
            row = UsageRecordModel(
                org_id=org_id,
                period_start=period_start,
                period_end=period_end,
            )
            self._session.add(row)

        row.trace_count = trace_count
        row.trace_eval_count = trace_eval_count
        row.session_eval_count = session_eval_count
        await self._session.flush()

    async def mark_billed(self, org_id: UUID, period_start: datetime, stripe_invoice_id: str | None) -> None:
        """Mark a usage record as billed with the Stripe invoice ID."""
        stmt = (
            update(UsageRecordModel)
            .where(
                UsageRecordModel.org_id == org_id,
                UsageRecordModel.period_start == period_start,
            )
            .values(billed=True, stripe_invoice_id=stripe_invoice_id)
        )
        await self._session.execute(stmt)

    async def update_reported_usage(
        self,
        org_id: UUID,
        period_start: datetime,
        *,
        reported_trace_count: int,
        reported_trace_eval_count: int,
        reported_session_eval_count: int,
    ) -> None:
        """Advance the high-water mark after reporting overages to Stripe."""
        stmt = (
            update(UsageRecordModel)
            .where(
                UsageRecordModel.org_id == org_id,
                UsageRecordModel.period_start == period_start,
            )
            .values(
                reported_trace_count=reported_trace_count,
                reported_trace_eval_count=reported_trace_eval_count,
                reported_session_eval_count=reported_session_eval_count,
            )
        )
        await self._session.execute(stmt)

    async def list_usage_history(self, org_id: UUID, *, limit: int = 12) -> list[UsageRecord]:
        """Return past usage records for an org, most recent first."""
        stmt = (
            select(UsageRecordModel)
            .where(UsageRecordModel.org_id == org_id)
            .order_by(UsageRecordModel.period_start.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_usage(r) for r in rows]

    # -- Member count helper --------------------------------------------------

    async def count_org_members(self, org_id: UUID) -> int:
        """Count active memberships for an organization."""
        from app.infrastructure.db.models import MembershipModel

        stmt = select(func.count()).where(MembershipModel.org_id == org_id)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    # -- Mappers --------------------------------------------------------------

    @staticmethod
    def _to_subscription(row: SubscriptionModel) -> Subscription:
        return Subscription(
            id=row.id,
            org_id=row.org_id,
            plan=SubscriptionPlan(row.plan),
            status=SubscriptionStatus(row.status),
            stripe_customer_id=row.stripe_customer_id,
            stripe_subscription_id=row.stripe_subscription_id,
            current_period_start=row.current_period_start,
            current_period_end=row.current_period_end,
            canceled_at=row.canceled_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _to_usage(row: UsageRecordModel) -> UsageRecord:
        return UsageRecord(
            id=row.id,
            org_id=row.org_id,
            period_start=row.period_start,
            period_end=row.period_end,
            trace_count=row.trace_count,
            trace_eval_count=row.trace_eval_count,
            session_eval_count=row.session_eval_count,
            reported_trace_count=row.reported_trace_count,
            reported_trace_eval_count=row.reported_trace_eval_count,
            reported_session_eval_count=row.reported_session_eval_count,
            billed=row.billed,
            stripe_invoice_id=row.stripe_invoice_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
