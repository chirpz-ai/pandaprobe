"""Durable overage intents and their Stripe delivery state."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.billing.entities import BillingReport, UsageRecord
from app.infrastructure.db.models import BillingReportModel, UsageRecordModel


class BillingReportRepository:
    """Serialize reservations on the usage row; serialize deliveries on each report."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def lock_usage(self, org_id: UUID, period_start: datetime) -> UsageRecord | None:
        """Reserve a period while calculating the next non-overlapping charge."""
        row = (
            await self._session.execute(
                select(UsageRecordModel)
                .where(UsageRecordModel.org_id == org_id, UsageRecordModel.period_start == period_start)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        return UsageRecord.model_validate(row, from_attributes=True) if row else None

    async def list_for_usage(self, usage_id: UUID) -> list[BillingReport]:
        """Return reservations, including undelivered ones, for a locked period."""
        rows = (
            (
                await self._session.execute(
                    select(BillingReportModel)
                    .where(BillingReportModel.usage_record_id == usage_id)
                    .order_by(BillingReportModel.created_at, BillingReportModel.id)
                )
            )
            .scalars()
            .all()
        )
        return [BillingReport.model_validate(row, from_attributes=True) for row in rows]

    async def create(self, **fields: object) -> BillingReport:
        """Stage an intent in the caller's transaction; never commit here."""
        row = BillingReportModel(**fields)
        self._session.add(row)
        await self._session.flush()
        return BillingReport.model_validate(row, from_attributes=True)

    async def lock_report(self, report_id: UUID) -> BillingReport | None:
        """Skip a report another worker is delivering instead of blocking a child."""
        row = (
            await self._session.execute(
                select(BillingReportModel)
                .where(BillingReportModel.id == report_id)
                .with_for_update(skip_locked=True)
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        return BillingReport.model_validate(row, from_attributes=True) if row else None

    async def update(self, report_id: UUID, **fields: object) -> None:
        """Update a locked report's delivery state."""
        await self._session.execute(
            update(BillingReportModel).where(BillingReportModel.id == report_id).values(**fields)
        )

    async def finish(self, report: BillingReport) -> None:
        """Record confirmation without regressing watermarks from newer reports."""
        # Later batches may arrive first. Do not move a high-water mark past an
        # earlier unresolved charge, even though its durable reservation is safe.
        usage = (
            await self._session.execute(
                select(UsageRecordModel).where(UsageRecordModel.id == report.usage_record_id).with_for_update()
            )
        ).scalar_one()
        reports = await self.list_for_usage(report.usage_record_id)
        watermarks = {}
        for category, counter in (
            ("traces", "trace_count"),
            ("trace_evals", "trace_eval_count"),
            ("session_evals", "session_eval_count"),
        ):
            confirmed = max(
                [getattr(usage, f"reported_{counter}")]
                + [getattr(r, f"snapshot_{counter}") for r in reports if r.status == "reported" or r.id == report.id]
            )
            unresolved = [
                int(r.requests[category]["metadata"]["from_count"])
                for r in reports
                if category in r.requests and category not in r.stripe_item_ids
            ]
            watermarks[f"reported_{counter}"] = max(
                getattr(usage, f"reported_{counter}"), min([confirmed] + unresolved)
            )
        await self._session.execute(
            update(UsageRecordModel).where(UsageRecordModel.id == report.usage_record_id).values(**watermarks)
        )
        await self.update(report.id, status="reported", last_error=None)

    async def pending_ids(self, *, limit: int = 200) -> list[UUID]:
        """Fetch a bounded retry batch, oldest last attempt first for fairness."""
        return list(
            (
                await self._session.execute(
                    select(BillingReportModel.id)
                    .where(BillingReportModel.status == "pending")
                    .order_by(BillingReportModel.updated_at, BillingReportModel.id)
                    .limit(limit)
                )
            )
            .scalars()
            .all()
        )

    async def recent_closures(self, since: datetime) -> list[tuple[UUID, datetime, datetime, UUID]]:
        """Follow up only explicitly closed periods, never automatically rebill legacy history."""
        rows = (
            await self._session.execute(
                select(
                    UsageRecordModel.org_id,
                    UsageRecordModel.period_start,
                    UsageRecordModel.period_end,
                    BillingReportModel.id,
                )
                .join(BillingReportModel, BillingReportModel.usage_record_id == UsageRecordModel.id)
                .where(BillingReportModel.closing_invoice_id.is_not(None), BillingReportModel.created_at >= since)
                .order_by(BillingReportModel.updated_at, BillingReportModel.id)
                .limit(200)
            )
        ).all()
        return [tuple(row) for row in rows]
