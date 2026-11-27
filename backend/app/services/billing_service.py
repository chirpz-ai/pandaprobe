"""Billing service: Stripe integration and overage calculations.

Handles checkout session creation, overage billing, and Stripe
webhook event processing for subscription lifecycle management.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import redis.asyncio as aioredis
import stripe
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.billing.entities import BillingResponse, CategoryUsage, OverageDetail, Subscription, UsageRecord
from app.core.billing.plans import get_plan_config, overage_by_item, plan_pricing, usd_cents
from app.infrastructure.db.repositories.billing_repo import BillingRepository
from app.infrastructure.db.repositories.billing_report_repo import BillingReportRepository
from app.infrastructure.redis.locks import acquire_owned_lock, release_owned_lock
from app.logging import logger
from app.registry.constants import (
    OVERAGE_LOCK_PREFIX,
    OVERAGE_LOCK_TTL,
    SUB_CACHE_PREFIX,
    SUB_CACHE_TTL,
    SubscriptionPlan,
    SubscriptionStatus,
)
from app.registry.exceptions import NotFoundError, PandaProbeError
from app.registry.settings import settings
from app.services.usage_service import UsageService

_stripe_configured = False

#: Transport config, applied once at first use (no network I/O). The SDK's own
#: default read timeout is 80s, which retries can multiply — long enough to wedge a Celery prefork child.
_STRIPE_TIMEOUT_S = 20
_STRIPE_MAX_RETRIES = 2

#: Must match the Stripe webhook endpoint's version, or payload and response shapes
#: diverge and moved fields read back as ``None``. See ``test_stripe_api_contract``.
STRIPE_API_VERSION = "2026-03-25.dahlia"

#: The only ``billing_reason`` that closes a period; the rest invoice within one.
_RENEWAL_BILLING_REASON = "subscription_cycle"


class StripeNotConfiguredError(PandaProbeError):
    """Raised when a Stripe operation is attempted without an API key.

    Surfacing this as its own error keeps a *configuration* fault from looking
    like a transient API fault: a missing key used to reach Stripe, come back
    401, and be retried, so a deploy that forgot the secret presented as an
    endless retry storm rather than an obvious misconfiguration.

    Subclasses ``PandaProbeError`` so the handler in ``main.py`` renders it as a
    503 instead of letting it escape as an unhandled 500 — which on the Stripe
    webhook route would make Stripe retry the delivery.
    """

    status_code = 503
    detail = "Billing is not configured on this deployment."


def _ensure_stripe_configured() -> None:
    """Assign the Stripe API key, version, timeout, and retry policy. Idempotent.

    Pure local assignment — this contacts nothing. ``RequestsClient`` is the
    SDK's HTTP *transport*, not an API client; constructing it only stores a
    timeout and the ``requests`` module. The first real network call happens
    later, at the ``stripe.*.create()`` that the caller makes.

    Runs once per process (guarded by ``_stripe_configured``), so the underlying
    ``requests.Session`` is reused and connection pooling to Stripe is preserved.
    """
    global _stripe_configured
    if _stripe_configured:
        return
    if not settings.STRIPE_SECRET_KEY:
        raise StripeNotConfiguredError(
            "STRIPE_SECRET_KEY is not set; this service cannot call Stripe. "
            "Cloud Run services that run billing tasks need the stripe-secret-key "
            "secret mounted (see worker_secret_env in the deploy Terraform)."
        )
    from stripe._http_client import RequestsClient

    stripe.api_key = settings.STRIPE_SECRET_KEY
    stripe.api_version = STRIPE_API_VERSION
    stripe.max_network_retries = _STRIPE_MAX_RETRIES
    stripe.default_http_client = RequestsClient(timeout=_STRIPE_TIMEOUT_S)
    _stripe_configured = True


def _resolve_plan_from_price_id(price_id: str) -> SubscriptionPlan | None:
    """Map a Stripe price ID to a local plan. Returns None if unrecognised."""
    mapping = {
        settings.STRIPE_STARTUP_PRICE_ID: SubscriptionPlan.STARTUP,
    }
    return mapping.get(price_id)


def _invoice_subscription_id(invoice: object) -> str | None:
    """Extract the subscription ID from a Stripe Invoice, or None if there is none.

    The same Basil-generation change that moved the billing period onto
    subscription items (see ``_get_sub_period``) also removed the Invoice's
    top-level ``subscription`` field, relocating it to
    ``parent.subscription_details.subscription``.

    Reading the old path against a Basil-or-later payload yields ``None``, which
    the invoice webhook handlers treat as "not a subscription invoice" and skip.
    That silently stopped every ``invoice.paid`` from marking its period billed.

    The legacy top-level path is kept as a fallback so this works against both
    shapes, which makes it safe regardless of the webhook endpoint's version.
    """
    parent = getattr(invoice, "parent", None)
    details = getattr(parent, "subscription_details", None)
    subscription = getattr(details, "subscription", None)
    if subscription is None:
        subscription = getattr(invoice, "subscription", None)
    # Either shape may hand back an expanded Subscription instead of a bare ID.
    if subscription is None or isinstance(subscription, str):
        return subscription
    return getattr(subscription, "id", None)


def _get_sub_period(stripe_sub: object) -> tuple[datetime, datetime]:
    """Extract billing period timestamps from a Stripe Subscription object.

    In API versions >= 2025-07-30.basil the top-level
    ``current_period_start``/``current_period_end`` fields were removed.
    The period now lives on each subscription *item*.
    """
    item = stripe_sub.items.data[0]  # type: ignore[attr-defined]
    return (
        datetime.fromtimestamp(item.current_period_start, tz=timezone.utc),
        datetime.fromtimestamp(item.current_period_end, tz=timezone.utc),
    )


def _invoice_period(invoice: object) -> tuple[datetime, datetime]:
    """Read the ending renewal period, never the subscription's mutable period."""
    start = getattr(invoice, "period_start", None)
    end = getattr(invoice, "period_end", None)
    if type(start) is not int or type(end) is not int or not 0 < start < end:
        raise PandaProbeError("Renewal invoice has no valid billing period; reconciliation required.")
    return datetime.fromtimestamp(start, timezone.utc), datetime.fromtimestamp(end, timezone.utc)


async def get_billing_overview(org_id: UUID, session: AsyncSession, redis_client: aioredis.Redis) -> BillingResponse:
    """Read usage and pricing for one period, including on deployments without Stripe credentials."""
    repo = BillingRepository(session)
    sub = await repo.get_subscription_by_org(org_id)
    if sub is None:
        raise NotFoundError("No subscription found for this organization.")

    counts = await UsageService(redis_client, session).get_period_counts(org_id, sub.current_period_start)
    total_events = sum(counts.values())
    usage = await repo.get_current_usage_record(org_id, sub.current_period_start)
    reports = await BillingReportRepository(session).list_for_usage(usage.id) if usage else []
    pricing = reports[0].pricing if reports else plan_pricing(sub.plan)
    plan = get_plan_config(sub.plan)
    pay_as_you_go = bool(reports) or plan.pay_as_you_go
    if "included_events" in pricing:
        included = pricing["included_events"]
        remaining = None if included is None else max(0, included - total_events)
    else:
        # Category-priced periods can exhaust one allowance while another still has room.
        included = sum(pricing[category] for category in counts)
        remaining = sum(max(0, pricing[category] - count) for category, count in counts.items())

    overage_events = sum(overage_by_item(counts, pricing).values()) if pay_as_you_go else 0
    rate = Decimal(pricing["unit_price"])
    # Stripe can confirm a later report before the earlier one advances the reported counters.
    reported_cents = sum(r.requests[item]["amount"] for r in reports for item in r.stripe_item_ids)
    if usage and not reports and pay_as_you_go:
        reported_cents = usd_cents(rate * sum(overage_by_item(usage.reported_counts, pricing).values()))
    # A rollback can lower live usage after a pooled charge has already been reserved.
    pending_reserved_cents = sum(
        r.requests["events"]["amount"] for r in reports if "events" in r.requests and "events" not in r.stripe_item_ids
    )
    estimated_cents = max(usd_cents(rate * overage_events), reported_cents + pending_reserved_cents)

    return BillingResponse(
        plan=sub.plan,
        period_start=sub.current_period_start.isoformat(),
        period_end=sub.current_period_end.isoformat(),
        base_price_cents=plan.monthly_price_cents,
        pay_as_you_go=pay_as_you_go,
        overage_unit_price=str(rate),
        traces=CategoryUsage(used=counts["traces"]),
        trace_evals=CategoryUsage(used=counts["trace_evals"]),
        session_evals=CategoryUsage(used=counts["session_evals"]),
        total_events=total_events,
        included_events=included,
        remaining_events=remaining,
        overage_events=overage_events,
        total_overage_cost=str(Decimal(estimated_cents) / 100),
        reported_overage_cost=str(Decimal(reported_cents) / 100),
        pending_overage_cost=str(Decimal(estimated_cents - reported_cents) / 100),
        estimated_total_cents=plan.monthly_price_cents + estimated_cents,
    )


class BillingService:
    """Orchestrates Stripe billing operations and overage calculations."""

    def __init__(self, session: AsyncSession, *, redis_client: aioredis.Redis | None = None) -> None:
        self._session = session
        self._repo = BillingRepository(session)
        self._redis = redis_client
        self._overage_lock_tokens: dict[UUID, str] = {}
        _ensure_stripe_configured()

    async def _warm_sub_cache(self, org_id: UUID) -> None:
        """Best-effort: re-read subscription from DB and write to Redis cache.

        Exceptions are swallowed so a cache failure after a successful
        DB commit never propagates to the caller (which would delete the
        webhook idempotency key and trigger a spurious Stripe retry).
        """
        if self._redis is None:
            return
        try:
            cache_key = f"{SUB_CACHE_PREFIX}{org_id}"
            sub = await self._repo.get_subscription_by_org(org_id)
            if sub is None:
                await self._redis.delete(cache_key)
                return
            payload = sub.model_dump(mode="json")
            await self._redis.set(cache_key, json.dumps(payload), ex=SUB_CACHE_TTL)
        except Exception:
            logger.warning("warm_sub_cache_failed", org_id=str(org_id))

    # -- Overage lock ---------------------------------------------------------

    async def acquire_overage_lock(self, org_id: UUID) -> bool:
        """Acquire a short-lived Redis lock to prevent concurrent overage reporting."""
        if self._redis is None:
            return True
        token = uuid4().hex
        acquired = await acquire_owned_lock(
            self._redis,
            f"{OVERAGE_LOCK_PREFIX}{org_id}",
            token,
            ttl=OVERAGE_LOCK_TTL,
        )
        if acquired:
            self._overage_lock_tokens[org_id] = token
        return acquired

    async def release_overage_lock(self, org_id: UUID) -> None:
        """Release the per-org overage reporting lock."""
        if self._redis is None:
            return
        token = self._overage_lock_tokens.get(org_id)
        if token is None:
            return
        await release_owned_lock(self._redis, f"{OVERAGE_LOCK_PREFIX}{org_id}", token)
        self._overage_lock_tokens.pop(org_id, None)

    # -- Checkout & Portal ----------------------------------------------------

    async def create_checkout_session(
        self,
        org_id: UUID,
        plan: SubscriptionPlan,
        *,
        success_url: str,
        cancel_url: str,
    ) -> str:
        """Create a Stripe Checkout Session and return its URL.

        If the org already has a Stripe customer, reuse it.
        Otherwise Stripe auto-creates one from the checkout.
        """
        if plan != SubscriptionPlan.STARTUP:
            raise ValueError("Checkout is only available for STARTUP plans.")

        price_id = settings.STRIPE_STARTUP_PRICE_ID

        sub = await self._repo.get_subscription_by_org(org_id)

        params: dict = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "automatic_tax": {"enabled": True},
            "allow_promotion_codes": True,
            "metadata": {"org_id": str(org_id), "plan": plan.value},
        }
        if sub and sub.stripe_customer_id:
            params["customer"] = sub.stripe_customer_id

        checkout = stripe.checkout.Session.create(**params)
        return checkout.url  # type: ignore[return-value]

    async def create_portal_session(self, org_id: UUID, *, return_url: str) -> str:
        """Create a Stripe Customer Portal session for self-service management."""
        from app.registry.exceptions import ValidationError

        sub = await self._repo.get_subscription_by_org(org_id)
        if sub is None or sub.stripe_customer_id is None:
            raise ValidationError(
                "No billing account exists for this organization. Upgrade to a paid plan to access billing management."
            )

        session = stripe.billing_portal.Session.create(
            customer=sub.stripe_customer_id,
            return_url=return_url,
        )
        return session.url  # type: ignore[return-value]

    # -- Overage calculation --------------------------------------------------

    async def calculate_unreported_overages(
        self, org_id: UUID, *, period_start: datetime | None = None
    ) -> OverageDetail:
        """Calculate NEW overage charges not yet reported to Stripe.

        Uses a high-water mark (``reported_*_count``) to compute only
        the delta since the last successful report, preventing double-billing.
        """
        sub = await self._repo.get_subscription_by_org(org_id)
        if sub is None:
            return OverageDetail()

        usage = await self._repo.get_current_usage_record(org_id, period_start or sub.current_period_start)
        if usage is None or usage.billed:
            return OverageDetail()

        reports = await BillingReportRepository(self._session).list_for_usage(usage.id)
        if not reports and not get_plan_config(sub.plan).pay_as_you_go:
            return OverageDetail()
        pricing = reports[0].pricing if reports else plan_pricing(sub.plan)
        current = overage_by_item(usage.counts, pricing)
        reported = overage_by_item(usage.reported_counts, pricing)
        events = sum(max(0, units - reported[item]) for item, units in current.items())
        return OverageDetail(
            overage_events=events,
            total_cost=Decimal(pricing["unit_price"]) * events,
            snapshot_trace_count=usage.trace_count,
            snapshot_trace_eval_count=usage.trace_eval_count,
            snapshot_session_eval_count=usage.session_eval_count,
        )

    async def report_overages_to_stripe(
        self, org_id: UUID, *, period_start: datetime | None = None, invoice_id: str | None = None
    ) -> bool:
        """Reserve charges durably before attempting Stripe; failures remain retryable."""
        from app.services.billing_reporting_service import BillingReportingService

        sub = await self._repo.get_subscription_by_org(org_id)
        if sub is None or sub.stripe_customer_id is None:
            return False
        reporting = BillingReportingService(self._session)
        report = await reporting.stage(
            sub,
            period_start or sub.current_period_start,
            invoice_id=invoice_id,
        )
        await self._session.commit()
        return await reporting.deliver_safely(report.id) if report else False

    # -- Webhook event handlers -----------------------------------------------

    async def handle_checkout_completed(self, event_data: dict) -> None:
        """Process ``checkout.session.completed`` -- activate a paid subscription."""
        obj = event_data["object"]
        org_id = UUID(obj.metadata["org_id"])
        plan = SubscriptionPlan(obj.metadata["plan"])
        customer_id = obj.customer
        subscription_id = obj.subscription

        stripe_sub = stripe.Subscription.retrieve(subscription_id)
        period_start, period_end = _get_sub_period(stripe_sub)

        existing = await self._repo.get_subscription_by_org(org_id)
        if existing:
            await self._repo.update_subscription(
                org_id,
                plan=plan.value,
                status=SubscriptionStatus.ACTIVE.value,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                current_period_start=period_start,
                current_period_end=period_end,
                canceled_at=None,
            )
        else:
            await self._repo.create_subscription(
                org_id=org_id,
                plan=plan,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                period_start=period_start,
                period_end=period_end,
            )

        await self._repo.get_or_create_usage_record(org_id, period_start, period_end)
        await self._session.commit()
        await self._warm_sub_cache(org_id)
        logger.info("checkout_completed", org_id=str(org_id), plan=plan.value)

    async def _sync_invoice_period(self, sub: Subscription, obj: object) -> UsageRecord:
        """Sync the ending period; missing or mismatched history needs reconciliation."""
        period_start, period_end = _invoice_period(obj)
        usage = await self._repo.get_current_usage_record(sub.org_id, period_start)
        if usage is not None and usage.period_end != period_end:
            raise PandaProbeError("Invoice period does not match usage history; reconciliation required.")
        if usage is not None and usage.billed:
            return usage
        if self._redis is not None:
            await UsageService(self._redis, self._session).sync_to_database(
                sub.org_id, period_start=period_start, period_end=period_end
            )
            await self._session.flush()
        usage = await self._repo.get_current_usage_record(sub.org_id, period_start)
        if usage is None:
            raise PandaProbeError("Invoice usage history is missing; reconciliation required.")
        return usage

    async def handle_invoice_created(self, event_data: dict) -> None:
        """Process ``invoice.created`` -- last-chance overage capture.

        Stripe fires this ~1 hour before the invoice is finalized.
        Target this invoice while it is still draft. If it has finalized,
        preserve the charge as carryover for the next subscription invoice.
        """
        obj = event_data["object"]
        if getattr(obj, "billing_reason", None) != _RENEWAL_BILLING_REASON:
            return
        subscription_id = _invoice_subscription_id(obj)
        if not subscription_id:
            return

        sub = await self._repo.get_subscription_by_stripe_subscription(subscription_id)
        if sub is None:
            return

        if not await self.acquire_overage_lock(sub.org_id):
            raise PandaProbeError("Overage reporting is busy; retry the invoice webhook.")
        try:
            usage = await self._sync_invoice_period(sub, obj)
            if not usage.billed:
                await self.report_overages_to_stripe(sub.org_id, period_start=usage.period_start, invoice_id=obj.id)
            await self._session.commit()
        finally:
            await self.release_overage_lock(sub.org_id)

        logger.info("invoice_created_overages_synced", org_id=str(sub.org_id))

    async def handle_invoice_paid(self, event_data: dict) -> None:
        """Close the invoice's ending period without billing a different month."""
        obj = event_data["object"]
        subscription_id = _invoice_subscription_id(obj)
        invoice_id = obj.id

        if not subscription_id:
            return

        sub = await self._repo.get_subscription_by_stripe_subscription(subscription_id)
        if sub is None:
            logger.warning("invoice_paid_unknown_subscription", subscription_id=subscription_id)
            return

        # Resolve the subscription before taking usage locks or staging charges.
        # Renewal and its reporting obligations are then committed together.
        stripe_sub = stripe.Subscription.retrieve(subscription_id)
        new_start, new_end = _get_sub_period(stripe_sub)

        # Only a renewal closes a period: ``calculate_unreported_overages`` skips
        # billed records, so closing the period a signup invoice *opens* would make
        # that customer's whole first month of overage unbillable.
        if getattr(obj, "billing_reason", None) == _RENEWAL_BILLING_REASON:
            if not await self.acquire_overage_lock(sub.org_id):
                raise PandaProbeError("Overage reporting is busy; retry the invoice webhook.")
            try:
                from app.services.billing_reporting_service import BillingReportingService

                usage = await self._sync_invoice_period(sub, obj)
                if not usage.billed:
                    await BillingReportingService(self._session).stage(
                        sub,
                        usage.period_start,
                        closing_invoice_id=invoice_id,
                    )
                    await self._repo.mark_billed(sub.org_id, usage.period_start, invoice_id)
                await self._repo.advance_period(sub.org_id, new_start, new_end)
                await self._repo.get_or_create_usage_record(sub.org_id, new_start, new_end)
                await self._repo.update_subscription(sub.org_id, status=SubscriptionStatus.ACTIVE.value)
                await self._session.commit()
            finally:
                await self.release_overage_lock(sub.org_id)
        else:
            await self._repo.advance_period(sub.org_id, new_start, new_end)
            await self._repo.get_or_create_usage_record(sub.org_id, new_start, new_end)
            await self._repo.update_subscription(sub.org_id, status=SubscriptionStatus.ACTIVE.value)
            await self._session.commit()
        await self._warm_sub_cache(sub.org_id)
        logger.info("invoice_paid", org_id=str(sub.org_id), invoice_id=invoice_id)

    async def handle_invoice_payment_failed(self, event_data: dict) -> None:
        """Process ``invoice.payment_failed`` -- mark subscription past due."""
        obj = event_data["object"]
        subscription_id = _invoice_subscription_id(obj)
        if not subscription_id:
            return

        sub = await self._repo.get_subscription_by_stripe_subscription(subscription_id)
        if sub is None:
            return

        await self._repo.update_subscription(sub.org_id, status=SubscriptionStatus.PAST_DUE.value)
        await self._session.commit()
        await self._warm_sub_cache(sub.org_id)
        logger.warning("invoice_payment_failed", org_id=str(sub.org_id))

    async def handle_subscription_updated(self, event_data: dict) -> None:
        """Process ``customer.subscription.updated`` -- plan/status changes."""
        obj = event_data["object"]
        subscription_id = obj.id
        sub = await self._repo.get_subscription_by_stripe_subscription(subscription_id)
        if sub is None:
            return

        new_status = getattr(obj, "status", "active")
        status_map = {
            "active": SubscriptionStatus.ACTIVE,
            "past_due": SubscriptionStatus.PAST_DUE,
            "canceled": SubscriptionStatus.CANCELED,
            "incomplete": SubscriptionStatus.INCOMPLETE,
        }
        mapped_status = status_map.get(new_status, SubscriptionStatus.ACTIVE)

        updates: dict = {"status": mapped_status.value}

        items_obj = getattr(obj, "items", None)
        items = items_obj.data if items_obj else []
        if items:
            price = getattr(items[0], "price", None)
            price_id = price.id if price else None
            if price_id:
                resolved_plan = _resolve_plan_from_price_id(price_id)
                if resolved_plan:
                    updates["plan"] = resolved_plan.value
                else:
                    logger.warning(
                        "subscription_updated_unknown_price",
                        org_id=str(sub.org_id),
                        price_id=price_id,
                    )

        stripe_canceled_at = getattr(obj, "canceled_at", None)
        updates["canceled_at"] = (
            datetime.fromtimestamp(stripe_canceled_at, tz=timezone.utc) if stripe_canceled_at else None
        )

        if items:
            first_item = items[0]
            period_start = getattr(first_item, "current_period_start", None)
            period_end = getattr(first_item, "current_period_end", None)
            if period_start and period_end:
                await self._repo.advance_period(
                    sub.org_id,
                    datetime.fromtimestamp(period_start, tz=timezone.utc),
                    datetime.fromtimestamp(period_end, tz=timezone.utc),
                )

        await self._repo.update_subscription(sub.org_id, **updates)
        await self._session.commit()
        await self._warm_sub_cache(sub.org_id)

        plan_label = updates.get("plan", sub.plan)
        logger.info(
            "subscription_updated",
            org_id=str(sub.org_id),
            status=mapped_status.value,
            plan=plan_label,
        )

    async def handle_subscription_deleted(self, event_data: dict) -> None:
        """Process ``customer.subscription.deleted`` -- finalize overages, then downgrade to HOBBY."""
        obj = event_data["object"]
        subscription_id = obj.id
        sub = await self._repo.get_subscription_by_stripe_subscription(subscription_id)
        if sub is None:
            return

        if sub.stripe_customer_id:
            if self._redis is not None:
                usage_svc = UsageService(self._redis, self._session)
                await usage_svc.sync_to_database(sub.org_id)
                await self._session.flush()

            if await self.acquire_overage_lock(sub.org_id):
                try:
                    await self.report_overages_to_stripe(sub.org_id)
                finally:
                    await self.release_overage_lock(sub.org_id)

            old_usage = await self._repo.get_current_usage_record(sub.org_id, sub.current_period_start)
            if old_usage and not old_usage.billed:
                await self._repo.mark_billed(sub.org_id, sub.current_period_start, stripe_invoice_id=None)

        now = datetime.now(timezone.utc)
        await self._repo.update_subscription(
            sub.org_id,
            plan=SubscriptionPlan.HOBBY.value,
            status=SubscriptionStatus.ACTIVE.value,
            stripe_subscription_id=None,
            canceled_at=now,
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
        )

        await self._repo.create_usage_record(sub.org_id, now, now + timedelta(days=30))
        await self._session.commit()
        await self._warm_sub_cache(sub.org_id)
        logger.info("subscription_deleted_downgraded", org_id=str(sub.org_id))
