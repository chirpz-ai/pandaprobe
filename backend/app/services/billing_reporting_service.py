"""Reserve overage charges transactionally and deliver them independently to Stripe.

Closing a usage period does not erase these obligations. Stripe requests are frozen
before sending; retries never recalculate an already reserved charge from live usage.
"""

from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from itertools import islice
from uuid import UUID, uuid4

import stripe
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.billing.entities import BillingReport, Subscription
from app.core.billing.plans import OVERAGE_UNIT_PRICE, get_plan_config
from app.infrastructure.db.repositories.billing_repo import BillingRepository
from app.infrastructure.db.repositories.billing_report_repo import BillingReportRepository
from app.logging import logger
from app.registry.exceptions import PandaProbeError

_COUNTERS = {
    "traces": ("trace_count", "base_traces", "Trace overage"),
    "trace_evals": ("trace_eval_count", "base_trace_evals", "Trace eval overage"),
    "session_evals": ("session_eval_count", "base_session_evals", "Session eval overage"),
}
_SAFE_RETRY_AGE = timedelta(hours=23)


class BillingReportingService:
    """Database-backed reporting; no broker message is the sole copy of a charge."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = BillingReportRepository(session)

    async def stage(
        self,
        sub: Subscription,
        period_start: datetime,
        *,
        invoice_id: str | None = None,
        closing_invoice_id: str | None = None,
        allow_closed: bool = False,
    ) -> BillingReport | None:
        """Reserve only unaccounted usage; commit alongside the caller's period update."""
        usage = await self._repo.lock_usage(sub.org_id, period_start)
        if usage is None or (usage.billed and not allow_closed):
            return None
        previous = await self._repo.list_for_usage(usage.id)
        if closing_invoice_id:
            existing = next((r for r in previous if r.closing_invoice_id == closing_invoice_id), None)
            if existing:
                return existing

        plan = get_plan_config(sub.plan)
        if not plan.pay_as_you_go and not previous:
            return None
        pricing = (
            previous[0].pricing
            if previous
            else {
                "unit_price": str(OVERAGE_UNIT_PRICE),
                **{category: getattr(plan, base) or 0 for category, (_, base, _) in _COUNTERS.items()},
            }
        )
        customer = previous[0].stripe_customer_id if previous else sub.stripe_customer_id
        subscription = previous[0].stripe_subscription_id if previous else sub.stripe_subscription_id
        if not customer:
            raise PandaProbeError("Cannot reserve billing usage without its Stripe customer.")

        report_id = uuid4()
        requests = {}
        snapshots = {}
        for category, (counter, _, description) in _COUNTERS.items():
            # Reservations count even if Stripe is down or an earlier attempt is ambiguous.
            reserved = max(
                [getattr(usage, f"reported_{counter}")] + [getattr(r, f"snapshot_{counter}") for r in previous]
            )
            snapshot = max(reserved, getattr(usage, counter))
            snapshots[f"snapshot_{counter}"] = snapshot
            base = pricing[category]
            units = max(0, snapshot - base) - max(0, reserved - base)
            if units <= 0:
                continue
            amount = int((Decimal(pricing["unit_price"]) * units * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            requests[category] = {
                "customer": customer,
                "currency": "usd",
                "amount": amount,
                "description": f"{description} ({units} units @ ${pricing['unit_price']}/unit); {usage.period_start.date()} to {usage.period_end.date()}",
                "period": {"start": int(usage.period_start.timestamp()), "end": int(usage.period_end.timestamp())},
                "metadata": {
                    "pp_report_id": str(report_id),
                    "category": category,
                    "org_id": str(sub.org_id),
                    "from_count": str(reserved),
                    "to_count": str(snapshot),
                },
                "idempotency_key": f"pp:report:{report_id}:{category}",
                **({"subscription": subscription} if subscription else {}),
                **({"invoice": invoice_id} if invoice_id else {}),
            }
        if not requests and not closing_invoice_id:
            return None
        # An empty closure marker enrolls this period for bounded late-counter checks.
        return await self._repo.create(
            id=report_id,
            usage_record_id=usage.id,
            stripe_customer_id=customer,
            stripe_subscription_id=subscription,
            closing_invoice_id=closing_invoice_id,
            pricing=pricing,
            requests=requests,
            status="pending" if requests else "reported",
            **snapshots,
        )

    async def _review(self, report: BillingReport, reason: str) -> None:
        await self._repo.update(report.id, status="needs_review", last_error=reason)
        await self._session.commit()
        logger.error("billing_report_needs_review", report_id=str(report.id), reason=reason)

    def _find_existing(self, report: BillingReport, category: str, attempted: datetime) -> stripe.InvoiceItem | None:
        """Find a prior success after idempotency expiry; absence is not proof of failure."""
        candidates = stripe.InvoiceItem.list(
            customer=report.stripe_customer_id, created={"gte": int(attempted.timestamp()) - 60}, limit=100
        ).auto_paging_iter()
        # Bound recovery work too. An inconclusive scan goes to review, never to
        # a blind new charge or an unbounded task occupying a worker child.
        for item in islice(candidates, 1000):
            if item.metadata.get("pp_report_id") == str(report.id) and item.metadata.get("category") == category:
                if item.amount != report.requests[category]["amount"] or item.currency != "usd":
                    raise PandaProbeError("Recovered Stripe item does not match the reserved charge.")
                return item
        return None

    async def deliver(self, report_id: UUID) -> bool:
        """Deliver a bounded (at most three items) report with crash-safe request identities."""
        while True:
            report = await self._repo.lock_report(report_id)
            if report is None or report.status != "pending":
                await self._session.rollback()
                return False
            category = next((c for c in report.requests if c not in report.stripe_item_ids), None)
            if category is None:
                await self._repo.finish(report)
                await self._session.commit()
                return True
            params = dict(report.requests[category])
            now = datetime.now(timezone.utc)
            attempted_str = report.attempted_at.get(category)

            if attempted_str is None:
                # Choose the destination before freezing the first request. Late draft
                # events become carryover; an already-attempted request never changes here.
                if params.get("invoice"):
                    invoice = stripe.Invoice.retrieve(params["invoice"])
                    if invoice.status != "draft":
                        params.pop("invoice")
                if not params.get("invoice") and report.stripe_subscription_id:
                    sub = await BillingRepository(self._session).get_subscription_by_org(
                        UUID(params["metadata"]["org_id"])
                    )
                    if (
                        sub is None
                        or sub.stripe_subscription_id != report.stripe_subscription_id
                        or sub.status == "CANCELED"
                    ):
                        await self._review(
                            report, "No continuing subscription to collect carryover; reconcile explicitly."
                        )
                        return False
                await self._repo.update(
                    report.id,
                    requests={**report.requests, category: params},
                    attempted_at={**report.attempted_at, category: now.isoformat()},
                )
                # Persist intent BEFORE network I/O. Reacquire the row lock after commit;
                # another worker may finish it meanwhile, in which case we exit above.
                await self._session.commit()
                continue

            attempted = datetime.fromisoformat(attempted_str)
            if now - attempted >= _SAFE_RETRY_AGE:
                try:
                    item = self._find_existing(report, category, attempted)
                except PandaProbeError as exc:
                    await self._review(report, str(exc))
                    return False
                if item is None:
                    await self._review(
                        report, "Stripe outcome unknown beyond safe idempotency window; do not blindly charge again."
                    )
                    return False
            else:
                try:
                    item = stripe.InvoiceItem.create(**params)
                except stripe.InvalidRequestError as exc:
                    # A definitive rejection because the target finalized (not a timeout)
                    # can be retried as carryover. A cached success would have returned it.
                    if params.get("invoice") and (exc.code == "invoice_not_editable" or exc.param == "invoice"):
                        invoice = stripe.Invoice.retrieve(params["invoice"])
                        if invoice.status != "draft":
                            params.pop("invoice")
                            params["idempotency_key"] += ":carryover"
                            attempts = dict(report.attempted_at)
                            attempts.pop(category)
                            await self._repo.update(
                                report.id, requests={**report.requests, category: params}, attempted_at=attempts
                            )
                            await self._session.commit()
                            continue
                    raise
            await self._repo.update(report.id, stripe_item_ids={**report.stripe_item_ids, category: item.id})
            await self._session.commit()

    async def deliver_safely(self, report_id: UUID) -> bool:
        """Keep durable failures retryable without turning Stripe downtime into failed renewal."""
        try:
            return await self.deliver(report_id)
        except Exception as exc:
            await self._session.rollback()
            report = await self._repo.lock_report(report_id)
            if report is not None and report.status == "pending":
                await self._repo.update(report.id, last_error=str(exc)[:2000])
                await self._session.commit()
            else:
                await self._session.rollback()
            logger.exception("billing_report_delivery_failed", report_id=str(report_id))
            return False
