"""Billing service: Stripe integration and overage calculations.

Handles checkout session creation, overage billing, and Stripe
webhook event processing for subscription lifecycle management.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

import redis.asyncio as aioredis
import stripe
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.billing.entities import OverageDetail, Subscription
from app.core.billing.plans import OVERAGE_UNIT_PRICE, get_plan_config
from app.infrastructure.db.repositories.billing_repo import BillingRepository
from app.logging import logger
from app.registry.constants import (
    OVERAGE_LOCK_PREFIX,
    OVERAGE_LOCK_TTL,
    SUB_CACHE_PREFIX,
    SUB_CACHE_TTL,
    SubscriptionPlan,
    SubscriptionStatus,
)
from app.registry.settings import settings

_stripe_configured = False


def _ensure_stripe_configured() -> None:
    """Set the stripe API key once at first use."""
    global _stripe_configured
    if not _stripe_configured:
        stripe.api_key = settings.STRIPE_SECRET_KEY
        _stripe_configured = True


def _resolve_plan_from_price_id(price_id: str) -> SubscriptionPlan | None:
    """Map a Stripe price ID to a local plan. Returns None if unrecognised."""
    mapping = {
        settings.STRIPE_PRO_PRICE_ID: SubscriptionPlan.PRO,
        settings.STRIPE_STARTUP_PRICE_ID: SubscriptionPlan.STARTUP,
    }
    return mapping.get(price_id)


class BillingService:
    """Orchestrates Stripe billing operations and overage calculations."""

    def __init__(self, session: AsyncSession, *, redis_client: aioredis.Redis | None = None) -> None:
        self._session = session
        self._repo = BillingRepository(session)
        self._redis = redis_client
        _ensure_stripe_configured()

    async def _warm_sub_cache(self, org_id: UUID) -> None:
        """Re-read the subscription from DB and write it into the Redis cache."""
        if self._redis is None:
            return
        cache_key = f"{SUB_CACHE_PREFIX}{org_id}"
        sub = await self._repo.get_subscription_by_org(org_id)
        if sub is None:
            await self._redis.delete(cache_key)
            return
        payload = sub.model_dump(mode="json")
        await self._redis.set(cache_key, json.dumps(payload), ex=SUB_CACHE_TTL)

    # -- Overage lock ---------------------------------------------------------

    async def acquire_overage_lock(self, org_id: UUID) -> bool:
        """Acquire a short-lived Redis lock to prevent concurrent overage reporting."""
        if self._redis is None:
            return True
        return bool(
            await self._redis.set(
                f"{OVERAGE_LOCK_PREFIX}{org_id}",
                "1",
                nx=True,
                ex=OVERAGE_LOCK_TTL,
            )
        )

    async def release_overage_lock(self, org_id: UUID) -> None:
        """Release the per-org overage reporting lock."""
        if self._redis is None:
            return
        await self._redis.delete(f"{OVERAGE_LOCK_PREFIX}{org_id}")

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
        if plan not in (SubscriptionPlan.PRO, SubscriptionPlan.STARTUP):
            raise ValueError("Checkout is only available for PRO and STARTUP plans.")

        price_id = settings.STRIPE_PRO_PRICE_ID if plan == SubscriptionPlan.PRO else settings.STRIPE_STARTUP_PRICE_ID

        sub = await self._repo.get_subscription_by_org(org_id)

        params: dict = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": {"org_id": str(org_id), "plan": plan.value},
        }
        if sub and sub.stripe_customer_id:
            params["customer"] = sub.stripe_customer_id

        checkout = stripe.checkout.Session.create(**params)
        return checkout.url  # type: ignore[return-value]

    async def create_portal_session(self, org_id: UUID, *, return_url: str) -> str:
        """Create a Stripe Customer Portal session for self-service management."""
        sub = await self._repo.get_subscription_by_org(org_id)
        if sub is None or sub.stripe_customer_id is None:
            raise ValueError("No Stripe customer found for this organization.")

        session = stripe.billing_portal.Session.create(
            customer=sub.stripe_customer_id,
            return_url=return_url,
        )
        return session.url  # type: ignore[return-value]

    # -- Overage calculation --------------------------------------------------

    async def calculate_unreported_overages(self, org_id: UUID) -> OverageDetail:
        """Calculate NEW overage charges not yet reported to Stripe.

        Uses a high-water mark (``reported_*_count``) to compute only
        the delta since the last successful report, preventing double-billing.
        """
        sub = await self._repo.get_subscription_by_org(org_id)
        if sub is None:
            return OverageDetail()

        plan_cfg = get_plan_config(SubscriptionPlan(sub.plan))
        if not plan_cfg.pay_as_you_go:
            return OverageDetail()

        usage = await self._repo.get_current_usage_record(org_id, sub.current_period_start)
        if usage is None or usage.billed:
            return OverageDetail()

        base_t = plan_cfg.base_traces or 0
        base_e = plan_cfg.base_trace_evals or 0
        base_s = plan_cfg.base_session_evals or 0

        total_t_over = max(0, usage.trace_count - base_t)
        total_e_over = max(0, usage.trace_eval_count - base_e)
        total_s_over = max(0, usage.session_eval_count - base_s)

        prev_t_over = max(0, usage.reported_trace_count - base_t)
        prev_e_over = max(0, usage.reported_trace_eval_count - base_e)
        prev_s_over = max(0, usage.reported_session_eval_count - base_s)

        dt = max(0, total_t_over - prev_t_over)
        de = max(0, total_e_over - prev_e_over)
        ds = max(0, total_s_over - prev_s_over)

        return OverageDetail(
            trace_overage=dt,
            trace_eval_overage=de,
            session_eval_overage=ds,
            trace_overage_cost=OVERAGE_UNIT_PRICE * dt,
            trace_eval_overage_cost=OVERAGE_UNIT_PRICE * de,
            session_eval_overage_cost=OVERAGE_UNIT_PRICE * ds,
            total_cost=OVERAGE_UNIT_PRICE * (dt + de + ds),
            snapshot_trace_count=usage.trace_count,
            snapshot_trace_eval_count=usage.trace_eval_count,
            snapshot_session_eval_count=usage.session_eval_count,
        )

    async def report_overages_to_stripe(self, org_id: UUID) -> bool:
        """Create Stripe InvoiceItems for the unreported overage delta.

        Ordering: Stripe items are created **before** the watermark is
        advanced.  If the DB commit fails after Stripe items exist, the
        next run re-creates the same delta (small, observable over-charge
        that self-corrects).  The reverse (watermark advanced, Stripe
        call fails) would silently lose revenue — hence this ordering.

        Returns ``True`` when items were created.
        """
        sub = await self._repo.get_subscription_by_org(org_id)
        if sub is None or sub.stripe_customer_id is None:
            return False

        overages = await self.calculate_unreported_overages(org_id)
        if overages.total_cost <= 0:
            return False

        items: list[tuple[str, int, Decimal]] = []
        if overages.trace_overage > 0:
            items.append(("Trace overage", overages.trace_overage, overages.trace_overage_cost))
        if overages.trace_eval_overage > 0:
            items.append(("Trace eval overage", overages.trace_eval_overage, overages.trace_eval_overage_cost))
        if overages.session_eval_overage > 0:
            items.append(("Session eval overage", overages.session_eval_overage, overages.session_eval_overage_cost))

        for description, qty, cost in items:
            amount_cents = int((cost * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            stripe.InvoiceItem.create(
                customer=sub.stripe_customer_id,
                amount=amount_cents,
                currency="usd",
                description=f"{description} ({qty} units @ ${OVERAGE_UNIT_PRICE}/unit)",
            )

        await self._repo.update_reported_usage(
            org_id=org_id,
            period_start=sub.current_period_start,
            reported_trace_count=overages.snapshot_trace_count,
            reported_trace_eval_count=overages.snapshot_trace_eval_count,
            reported_session_eval_count=overages.snapshot_session_eval_count,
        )

        logger.info(
            "overages_reported",
            org_id=str(org_id),
            total_cost=str(overages.total_cost),
            trace_delta=overages.trace_overage,
            eval_delta=overages.trace_eval_overage,
            sess_delta=overages.session_eval_overage,
        )
        return True

    # -- Webhook event handlers -----------------------------------------------

    async def handle_checkout_completed(self, event_data: dict) -> None:
        """Process ``checkout.session.completed`` -- activate a paid subscription."""
        obj = event_data["object"]
        org_id = UUID(obj["metadata"]["org_id"])
        plan = SubscriptionPlan(obj["metadata"]["plan"])
        customer_id = obj["customer"]
        subscription_id = obj["subscription"]

        stripe_sub = stripe.Subscription.retrieve(subscription_id)
        period_start = datetime.fromtimestamp(stripe_sub["current_period_start"], tz=timezone.utc)
        period_end = datetime.fromtimestamp(stripe_sub["current_period_end"], tz=timezone.utc)

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

    async def handle_invoice_created(self, event_data: dict) -> None:
        """Process ``invoice.created`` -- last-chance overage capture.

        Stripe fires this ~1 hour before the invoice is finalized.
        Items added here land on THIS invoice rather than spilling to
        the next billing period.
        """
        obj = event_data["object"]
        subscription_id = obj.get("subscription")
        if not subscription_id:
            return

        sub = await self._repo.get_subscription_by_stripe_subscription(subscription_id)
        if sub is None:
            return

        plan_cfg = get_plan_config(SubscriptionPlan(sub.plan))
        if not plan_cfg.pay_as_you_go:
            return

        if self._redis is not None:
            from app.services.usage_service import UsageService

            usage_svc = UsageService(self._redis, self._session)
            await usage_svc.sync_to_database(sub.org_id)
            await self._session.flush()

        if await self.acquire_overage_lock(sub.org_id):
            try:
                await self.report_overages_to_stripe(sub.org_id)
                await self._session.commit()
            finally:
                await self.release_overage_lock(sub.org_id)

        logger.info("invoice_created_overages_synced", org_id=str(sub.org_id))

    async def handle_invoice_paid(self, event_data: dict) -> None:
        """Process ``invoice.paid`` -- final overage report, then advance billing period."""
        obj = event_data["object"]
        subscription_id = obj.get("subscription")
        invoice_id = obj["id"]

        if not subscription_id:
            return

        sub = await self._repo.get_subscription_by_stripe_subscription(subscription_id)
        if sub is None:
            logger.warning("invoice_paid_unknown_subscription", subscription_id=subscription_id)
            return

        # Final sync: flush Redis counters to DB so the delta calc is up-to-date
        if self._redis is not None:
            from app.services.usage_service import UsageService

            usage_svc = UsageService(self._redis, self._session)
            await usage_svc.sync_to_database(sub.org_id)
            await self._session.flush()

        # Report any remaining unreported overages for the ending period.
        # Items created here land on the *next* invoice (this one is already paid).
        if await self.acquire_overage_lock(sub.org_id):
            try:
                await self.report_overages_to_stripe(sub.org_id)
            finally:
                await self.release_overage_lock(sub.org_id)

        # Mark the ending period as fully billed
        old_usage = await self._repo.get_current_usage_record(sub.org_id, sub.current_period_start)
        if old_usage and not old_usage.billed:
            await self._repo.mark_billed(sub.org_id, sub.current_period_start, invoice_id)

        # Advance to the new billing period
        stripe_sub = stripe.Subscription.retrieve(subscription_id)
        new_start = datetime.fromtimestamp(stripe_sub["current_period_start"], tz=timezone.utc)
        new_end = datetime.fromtimestamp(stripe_sub["current_period_end"], tz=timezone.utc)

        await self._repo.advance_period(sub.org_id, new_start, new_end)
        await self._repo.get_or_create_usage_record(sub.org_id, new_start, new_end)
        await self._repo.update_subscription(sub.org_id, status=SubscriptionStatus.ACTIVE.value)
        await self._session.commit()
        await self._warm_sub_cache(sub.org_id)
        logger.info("invoice_paid", org_id=str(sub.org_id), invoice_id=invoice_id)

    async def handle_invoice_payment_failed(self, event_data: dict) -> None:
        """Process ``invoice.payment_failed`` -- mark subscription past due."""
        obj = event_data["object"]
        subscription_id = obj.get("subscription")
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
        subscription_id = obj["id"]
        sub = await self._repo.get_subscription_by_stripe_subscription(subscription_id)
        if sub is None:
            return

        new_status = obj.get("status", "active")
        status_map = {
            "active": SubscriptionStatus.ACTIVE,
            "past_due": SubscriptionStatus.PAST_DUE,
            "canceled": SubscriptionStatus.CANCELED,
            "incomplete": SubscriptionStatus.INCOMPLETE,
        }
        mapped_status = status_map.get(new_status, SubscriptionStatus.ACTIVE)

        updates: dict = {"status": mapped_status.value}

        items = obj.get("items", {}).get("data", [])
        if items:
            price_id = items[0].get("price", {}).get("id")
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

        cancel_at = obj.get("cancel_at")
        if cancel_at:
            updates["canceled_at"] = datetime.fromtimestamp(cancel_at, tz=timezone.utc)

        period_start = obj.get("current_period_start")
        period_end = obj.get("current_period_end")
        if period_start:
            updates["current_period_start"] = datetime.fromtimestamp(period_start, tz=timezone.utc)
        if period_end:
            updates["current_period_end"] = datetime.fromtimestamp(period_end, tz=timezone.utc)

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
        subscription_id = obj["id"]
        sub = await self._repo.get_subscription_by_stripe_subscription(subscription_id)
        if sub is None:
            return

        plan_cfg = get_plan_config(SubscriptionPlan(sub.plan))
        if plan_cfg.pay_as_you_go and sub.stripe_customer_id:
            if self._redis is not None:
                from app.services.usage_service import UsageService

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
