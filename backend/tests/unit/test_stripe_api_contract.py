"""Contract tests for the pinned Stripe API version (no infra required).

``billing_service`` is written against one pinned API version, which must match
the version configured on the Stripe webhook endpoint.  Stripe moves fields
between generations, and a moved field reads back as ``None`` rather than
raising — so a mismatch shows up as a handler silently doing nothing.

That is not hypothetical: the Basil generation relocated
``Invoice.subscription`` to ``parent.subscription_details.subscription``, and the
invoice handlers kept reading the old path.  Every ``invoice.paid`` exited early,
so no billing period was ever marked billed and each period's trailing overage
went unbilled.

These tests pin two things:

1. every Stripe field the service reads still exists in the installed SDK, so a
   version or SDK bump fails here instead of in production;
2. the invoice handlers actually act on a payload shaped like the pinned
   version.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
import stripe

from app.core.billing.entities import Subscription, UsageRecord
from app.registry.constants import SubscriptionPlan, SubscriptionStatus
from app.services.billing_service import (
    STRIPE_API_VERSION,
    BillingService,
    _invoice_subscription_id,
)

# ---------------------------------------------------------------------------
# Payload fixtures
#
# Copied from real objects fetched from the live account at
# ``2026-03-25.dahlia`` — note the absent top-level ``subscription``.
# ---------------------------------------------------------------------------

_SUB_ID = "sub_1TR44d383qTt3y6KDWXCEL2U"

#: A renewal invoice — the one kind that closes the period it was billed for.
_DAHLIA_INVOICE = {
    "id": "in_1Ty3SI383qTt3y6Kam9NvvmQ",
    "object": "invoice",
    "customer": "cus_TEST",
    "status": "paid",
    "amount_paid": 0,
    "billing_reason": "subscription_cycle",
    "parent": {
        "quote_details": None,
        "subscription_details": {"metadata": {}, "subscription": _SUB_ID},
        "type": "subscription_details",
    },
}

#: The invoice Stripe pays at signup. Observed on the live account with a
#: zero-length period, because it opens a billing period rather than closing one.
_SIGNUP_INVOICE = {**_DAHLIA_INVOICE, "id": "in_SIGNUP", "billing_reason": "subscription_create"}

#: Pre-Basil shape, retained because the accessor keeps a legacy fallback.
_LEGACY_INVOICE = {
    "id": "in_LEGACY",
    "object": "invoice",
    "customer": "cus_TEST",
    "subscription": _SUB_ID,
}

#: A one-off invoice — not tied to any subscription. Handlers must skip these.
_ONE_OFF_INVOICE = {
    "id": "in_ONEOFF",
    "object": "invoice",
    "customer": "cus_TEST",
    "parent": None,
}


def _invoice(payload: dict) -> stripe.Invoice:
    """Build a Stripe object the way ``Webhook.construct_event`` would."""
    return stripe.Invoice.construct_from(payload, "sk_test_dummy")


# ---------------------------------------------------------------------------
# 1. Field-level contract against the installed SDK
# ---------------------------------------------------------------------------


def test_pinned_version_is_a_dahlia_generation_version() -> None:
    """The accessors below assume Dahlia-era shapes; keep the pin in that family."""
    assert STRIPE_API_VERSION.endswith(".dahlia")


@pytest.mark.parametrize(
    ("cls", "field"),
    [
        # Checkout Session — handle_checkout_completed
        (stripe.checkout.Session, "metadata"),
        (stripe.checkout.Session, "customer"),
        (stripe.checkout.Session, "subscription"),
        # Subscription — handle_subscription_updated / _get_sub_period
        (stripe.Subscription, "id"),
        (stripe.Subscription, "status"),
        (stripe.Subscription, "items"),
        (stripe.Subscription, "canceled_at"),
        # SubscriptionItem — where the billing period lives post-Basil
        (stripe.SubscriptionItem, "price"),
        (stripe.SubscriptionItem, "current_period_start"),
        (stripe.SubscriptionItem, "current_period_end"),
        # Invoice
        (stripe.Invoice, "id"),
        (stripe.Invoice, "parent"),
        # Distinguishes a renewal from a signup invoice; without it the handler
        # cannot tell whether a period is closing or opening.
        (stripe.Invoice, "billing_reason"),
    ],
)
def test_field_read_by_billing_service_still_exists(cls: type, field: str) -> None:
    """Fail loudly when Stripe moves a field the service depends on."""
    assert field in (getattr(cls, "__annotations__", {}) or {}), (
        f"{cls.__name__}.{field} is gone from the SDK — billing_service reads it. "
        "Check Stripe's API changelog for where it moved."
    )


@pytest.mark.parametrize(
    ("cls", "field"),
    [
        (stripe.Invoice, "subscription"),
        (stripe.Subscription, "current_period_start"),
    ],
)
def test_relocated_fields_are_still_absent(cls: type, field: str) -> None:
    """Guard the two fields whose relocation drove this module's accessors.

    If one of these reappears, the SDK or pin moved backwards and the accessors
    should be revisited rather than silently preferring the legacy path.
    """
    assert field not in (getattr(cls, "__annotations__", {}) or {})


# ---------------------------------------------------------------------------
# 2. The accessor
# ---------------------------------------------------------------------------


def test_reads_subscription_id_from_the_dahlia_location() -> None:
    assert _invoice_subscription_id(_invoice(_DAHLIA_INVOICE)) == _SUB_ID


def test_falls_back_to_the_legacy_top_level_field() -> None:
    """Keeps working if the webhook endpoint is pinned to a pre-Basil version."""
    assert _invoice_subscription_id(_invoice(_LEGACY_INVOICE)) == _SUB_ID


def test_returns_none_for_an_invoice_with_no_subscription() -> None:
    assert _invoice_subscription_id(_invoice(_ONE_OFF_INVOICE)) is None


def test_unwraps_an_expanded_subscription_object() -> None:
    """``subscription`` may be expanded into a full object rather than an ID."""
    payload = {
        "id": "in_EXPANDED",
        "object": "invoice",
        "parent": {
            "type": "subscription_details",
            "subscription_details": {"subscription": {"id": _SUB_ID, "object": "subscription"}},
        },
    }
    assert _invoice_subscription_id(_invoice(payload)) == _SUB_ID


# ---------------------------------------------------------------------------
# 3. Handlers act on a pinned-version payload
# ---------------------------------------------------------------------------


@pytest.fixture
def svc() -> BillingService:
    """A BillingService with the repo and session stubbed out."""
    service = BillingService(MagicMock())
    service._repo = AsyncMock()
    service._session = AsyncMock()
    return service


def _subscription(plan: SubscriptionPlan = SubscriptionPlan.PRO) -> Subscription:
    now = datetime(2026, 7, 28, tzinfo=timezone.utc)
    return Subscription(
        id=uuid4(),
        org_id=uuid4(),
        plan=plan,
        status=SubscriptionStatus.ACTIVE,
        stripe_customer_id="cus_TEST",
        stripe_subscription_id=_SUB_ID,
        current_period_start=now,
        current_period_end=datetime(2026, 8, 28, tzinfo=timezone.utc),
        created_at=now,
        updated_at=now,
    )


def _arrange_paid_invoice(svc: BillingService, monkeypatch: pytest.MonkeyPatch) -> Subscription:
    """Stub the repo reads and the two outbound Stripe calls on the paid path."""
    sub = _subscription()
    now = sub.current_period_start
    svc._repo.get_subscription_by_stripe_subscription.return_value = sub
    svc._repo.get_current_usage_record.return_value = UsageRecord(
        id=uuid4(),
        org_id=sub.org_id,
        period_start=now,
        period_end=sub.current_period_end,
        billed=False,
        created_at=now,
        updated_at=now,
    )
    monkeypatch.setattr(svc, "report_overages_to_stripe", AsyncMock(return_value=False))
    item = MagicMock(current_period_start=1790000000, current_period_end=1792592000)
    monkeypatch.setattr(stripe.Subscription, "retrieve", lambda *a, **k: MagicMock(items=MagicMock(data=[item])))
    return sub


async def test_invoice_paid_marks_the_period_billed(svc: BillingService, monkeypatch: pytest.MonkeyPatch) -> None:
    """The regression: this never ran, so history showed 'pending' forever."""
    _arrange_paid_invoice(svc, monkeypatch)

    await svc.handle_invoice_paid({"object": _invoice(_DAHLIA_INVOICE)})

    svc._repo.get_subscription_by_stripe_subscription.assert_awaited_once_with(_SUB_ID)
    assert svc._repo.mark_billed.await_count == 1, "a renewal must mark the closing period billed"
    assert svc._repo.advance_period.await_count == 1, "invoice.paid must advance the billing period"


async def test_signup_invoice_leaves_the_new_period_open(svc: BillingService, monkeypatch: pytest.MonkeyPatch) -> None:
    """A signup invoice opens a period; closing it would forfeit a month of overage.

    ``calculate_unreported_overages`` returns nothing once a record is billed, so
    marking the just-created period billed makes every overage unit the customer
    accrues that month permanently unbillable.
    """
    _arrange_paid_invoice(svc, monkeypatch)

    await svc.handle_invoice_paid({"object": _invoice(_SIGNUP_INVOICE)})

    assert svc._repo.mark_billed.await_count == 0, "signup must not close the period it opened"
    # The rest of the handler still runs: the period is refreshed and left billable.
    assert svc._repo.advance_period.await_count == 1


@pytest.mark.parametrize(
    ("billing_reason", "closes_period"),
    [
        ("subscription_cycle", True),  # renewal — the period genuinely ended
        ("subscription_create", False),  # signup
        ("subscription_update", False),  # mid-cycle proration
        ("subscription_threshold", False),  # billing threshold reached mid-cycle
        ("manual", False),  # one-off invoice raised against the customer
        (None, False),  # unknown shape: prefer a stale label over lost revenue
    ],
)
async def test_only_a_renewal_closes_the_billing_period(
    svc: BillingService,
    monkeypatch: pytest.MonkeyPatch,
    billing_reason: str | None,
    closes_period: bool,
) -> None:
    _arrange_paid_invoice(svc, monkeypatch)
    payload = {**_DAHLIA_INVOICE}
    if billing_reason is None:
        payload.pop("billing_reason")
    else:
        payload["billing_reason"] = billing_reason

    await svc.handle_invoice_paid({"object": _invoice(payload)})

    assert (svc._repo.mark_billed.await_count == 1) is closes_period


async def test_invoice_payment_failed_marks_past_due(svc: BillingService) -> None:
    sub = _subscription()
    svc._repo.get_subscription_by_stripe_subscription.return_value = sub

    await svc.handle_invoice_payment_failed({"object": _invoice(_DAHLIA_INVOICE)})

    svc._repo.update_subscription.assert_awaited_once_with(sub.org_id, status=SubscriptionStatus.PAST_DUE.value)


async def test_invoice_created_reaches_the_overage_sweep(svc: BillingService, monkeypatch: pytest.MonkeyPatch) -> None:
    """The last-chance sweep that kept each period's trailing overage billable."""
    sub = _subscription()
    svc._repo.get_subscription_by_stripe_subscription.return_value = sub
    reporter = AsyncMock(return_value=False)
    monkeypatch.setattr(svc, "report_overages_to_stripe", reporter)

    await svc.handle_invoice_created({"object": _invoice(_DAHLIA_INVOICE)})

    reporter.assert_awaited_once_with(sub.org_id)


@pytest.mark.parametrize(
    "handler_name",
    ["handle_invoice_created", "handle_invoice_paid", "handle_invoice_payment_failed"],
)
async def test_handlers_skip_invoices_with_no_subscription(svc: BillingService, handler_name: str) -> None:
    """One-off invoices must still be ignored, not treated as subscription renewals."""
    await getattr(svc, handler_name)({"object": _invoice(_ONE_OFF_INVOICE)})

    svc._repo.get_subscription_by_stripe_subscription.assert_not_awaited()
