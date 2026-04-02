"""Billing service: Stripe integration and overage calculations.

Handles checkout session creation, overage billing, and Stripe
webhook event processing for subscription lifecycle management.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import stripe
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.billing.entities import OverageDetail, Subscription
from app.core.billing.plans import OVERAGE_UNIT_PRICE, get_plan_config
from app.infrastructure.db.repositories.billing_repo import BillingRepository
from app.logging import logger
from app.registry.constants import SubscriptionPlan, SubscriptionStatus
from app.registry.settings import settings


def _stripe_client() -> None:
    """Configure the stripe module with the secret key."""
    stripe.api_key = settings.STRIPE_SECRET_KEY


class BillingService:
    """Orchestrates Stripe billing operations and overage calculations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = BillingRepository(session)
        _stripe_client()

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

        price_id = (
            settings.STRIPE_PRO_PRICE_ID
            if plan == SubscriptionPlan.PRO
            else settings.STRIPE_STARTUP_PRICE_ID
        )

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

    async def calculate_overages(self, org_id: UUID) -> OverageDetail:
        """Calculate overage charges for the current billing period."""
        sub = await self._repo.get_subscription_by_org(org_id)
        if sub is None:
            return OverageDetail()

        plan_cfg = get_plan_config(SubscriptionPlan(sub.plan))
        if not plan_cfg.pay_as_you_go:
            return OverageDetail()

        usage = await self._repo.get_current_usage_record(org_id, sub.current_period_start)
        if usage is None:
            return OverageDetail()

        trace_over = max(0, usage.trace_count - (plan_cfg.base_traces or 0))
        eval_over = max(0, usage.trace_eval_count - (plan_cfg.base_trace_evals or 0))
        sess_over = max(0, usage.session_eval_count - (plan_cfg.base_session_evals or 0))

        return OverageDetail(
            trace_overage=trace_over,
            trace_eval_overage=eval_over,
            session_eval_overage=sess_over,
            trace_overage_cost=OVERAGE_UNIT_PRICE * trace_over,
            trace_eval_overage_cost=OVERAGE_UNIT_PRICE * eval_over,
            session_eval_overage_cost=OVERAGE_UNIT_PRICE * sess_over,
            total_cost=OVERAGE_UNIT_PRICE * (trace_over + eval_over + sess_over),
        )

    async def report_overages_to_stripe(self, org_id: UUID) -> str | None:
        """Create Stripe Invoice Items for overages on the upcoming invoice.

        Returns the invoice ID if items were created, else None.
        """
        sub = await self._repo.get_subscription_by_org(org_id)
        if sub is None or sub.stripe_customer_id is None:
            return None

        overages = await self.calculate_overages(org_id)
        if overages.total_cost <= 0:
            return None

        items: list[tuple[str, int, Decimal]] = []
        if overages.trace_overage > 0:
            items.append(("Trace overage", overages.trace_overage, overages.trace_overage_cost))
        if overages.trace_eval_overage > 0:
            items.append(("Trace eval overage", overages.trace_eval_overage, overages.trace_eval_overage_cost))
        if overages.session_eval_overage > 0:
            items.append(("Session eval overage", overages.session_eval_overage, overages.session_eval_overage_cost))

        for description, qty, cost in items:
            stripe.InvoiceItem.create(
                customer=sub.stripe_customer_id,
                amount=int(cost * 100),
                currency="usd",
                description=f"{description} ({qty} units @ ${OVERAGE_UNIT_PRICE}/unit)",
            )

        logger.info(
            "overages_reported",
            org_id=str(org_id),
            total_cost=str(overages.total_cost),
        )

        await self._repo.mark_billed(
            org_id,
            sub.current_period_start,
            stripe_invoice_id="pending",
        )

        return "pending"

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
        logger.info("checkout_completed", org_id=str(org_id), plan=plan.value)

    async def handle_invoice_paid(self, event_data: dict) -> None:
        """Process ``invoice.paid`` -- advance billing period."""
        obj = event_data["object"]
        subscription_id = obj.get("subscription")
        invoice_id = obj["id"]

        if not subscription_id:
            return

        sub = await self._repo.get_subscription_by_stripe_subscription(subscription_id)
        if sub is None:
            logger.warning("invoice_paid_unknown_subscription", subscription_id=subscription_id)
            return

        stripe_sub = stripe.Subscription.retrieve(subscription_id)
        new_start = datetime.fromtimestamp(stripe_sub["current_period_start"], tz=timezone.utc)
        new_end = datetime.fromtimestamp(stripe_sub["current_period_end"], tz=timezone.utc)

        old_usage = await self._repo.get_current_usage_record(sub.org_id, sub.current_period_start)
        if old_usage and not old_usage.billed:
            await self._repo.mark_billed(sub.org_id, sub.current_period_start, invoice_id)

        await self._repo.advance_period(sub.org_id, new_start, new_end)
        await self._repo.get_or_create_usage_record(sub.org_id, new_start, new_end)
        await self._repo.update_subscription(
            sub.org_id, status=SubscriptionStatus.ACTIVE.value
        )
        await self._session.commit()
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
        logger.info("subscription_updated", org_id=str(sub.org_id), status=mapped_status.value)

    async def handle_subscription_deleted(self, event_data: dict) -> None:
        """Process ``customer.subscription.deleted`` -- downgrade to HOBBY."""
        obj = event_data["object"]
        subscription_id = obj["id"]
        sub = await self._repo.get_subscription_by_stripe_subscription(subscription_id)
        if sub is None:
            return

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

        await self._repo.create_usage_record(
            sub.org_id, now, now + timedelta(days=30)
        )
        await self._session.commit()
        logger.info("subscription_deleted_downgraded", org_id=str(sub.org_id))
