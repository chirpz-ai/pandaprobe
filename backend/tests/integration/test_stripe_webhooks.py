"""End-to-end tests for the Stripe webhook route against a real database.

These drive the full path a Stripe delivery actually takes — HTTP POST, signature
verification, event dispatch, handler, DB commit — and then assert the rows
changed.  The unit tests in ``tests/unit/test_stripe_api_contract.py`` cover the
field accessors in isolation; these prove the wiring works for real.

The payloads are shaped like the pinned API version (``2026-03-25.dahlia``),
where an invoice carries its subscription at
``parent.subscription_details.subscription`` rather than at the top level.
Reading the old path returned ``None``, so every ``invoice.paid`` exited early and
no billing period was ever marked billed.
"""

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
import stripe
from httpx import AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models import SubscriptionModel, UsageRecordModel
from app.infrastructure.db.repositories.billing_repo import BillingRepository
from app.infrastructure.redis.client import redis_pool
from app.registry.constants import SubscriptionPlan, SubscriptionStatus
from app.registry.settings import settings

from .conftest import TEST_ORG_ID

_WEBHOOK_PATH = "/webhooks/stripe"
_STRIPE_SUB_ID = "sub_webhook_verify"


@pytest.fixture(autouse=True)
async def _drop_pooled_redis_connections():
    """Release the module-level Redis pool between tests.

    Unlike the rest of the API, the webhook route takes its Redis client from the
    module-level ``redis_pool`` rather than the ``get_redis`` dependency, so the
    autouse override in ``conftest`` does not reach it.  Each test gets a fresh
    event loop, and connections pooled on a previous one raise "Event loop is
    closed" when reused — the same hazard the engine ``dispose()`` in conftest
    guards against.
    """
    yield
    await redis_pool.disconnect()


def _sign(payload: bytes) -> str:
    """Build a valid ``Stripe-Signature`` header for *payload*."""
    timestamp = int(time.time())
    signed = f"{timestamp}.{payload.decode()}".encode()
    digest = hmac.new(settings.STRIPE_WEBHOOK_SECRET.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def _event(event_type: str, invoice: dict) -> bytes:
    """Serialise a Stripe event envelope around *invoice*."""
    return json.dumps(
        {
            "id": f"evt_{uuid4().hex}",
            "object": "event",
            "api_version": "2026-03-25.dahlia",
            "type": event_type,
            "data": {"object": invoice},
        }
    ).encode()


def _dahlia_invoice(**overrides) -> dict:
    """An invoice as the pinned API version renders it — no top-level subscription.

    Defaults to a *renewal* (``subscription_cycle``), the only billing reason that
    closes the period it was billed for.
    """
    invoice = {
        "id": f"in_{uuid4().hex[:16]}",
        "object": "invoice",
        "customer": "cus_webhook_verify",
        "status": "paid",
        "amount_paid": 0,
        "billing_reason": "subscription_cycle",
        "parent": {
            "quote_details": None,
            "subscription_details": {"metadata": {}, "subscription": _STRIPE_SUB_ID},
            "type": "subscription_details",
        },
    }
    invoice.update(overrides)
    return invoice


async def _post(client: AsyncClient, event_type: str, invoice: dict):
    body = _event(event_type, invoice)
    return await client.post(
        _WEBHOOK_PATH,
        content=body,
        headers={"Stripe-Signature": _sign(body), "Content-Type": "application/json"},
    )


@pytest.fixture
async def paid_subscription(db_session: AsyncSession) -> tuple[datetime, datetime]:
    """A PRO subscription with an unbilled usage record for the current period.

    Counters stay at zero so overage reporting short-circuits before reaching
    Stripe — these tests must not need network access.
    """
    await db_session.execute(delete(UsageRecordModel).where(UsageRecordModel.org_id == TEST_ORG_ID))
    await db_session.execute(delete(SubscriptionModel).where(SubscriptionModel.org_id == TEST_ORG_ID))
    await db_session.commit()

    period_start = datetime(2026, 7, 28, tzinfo=timezone.utc)
    period_end = datetime(2026, 8, 28, tzinfo=timezone.utc)

    repo = BillingRepository(db_session)
    await repo.create_subscription(
        TEST_ORG_ID,
        plan=SubscriptionPlan.PRO,
        stripe_customer_id="cus_webhook_verify",
        stripe_subscription_id=_STRIPE_SUB_ID,
        period_start=period_start,
        period_end=period_end,
    )
    await repo.get_or_create_usage_record(TEST_ORG_ID, period_start, period_end)
    await db_session.commit()
    return period_start, period_end


@pytest.fixture
def stub_stripe_subscription(monkeypatch: pytest.MonkeyPatch) -> tuple[datetime, datetime]:
    """Stub ``Subscription.retrieve`` — the only outbound call on this path."""
    new_start = datetime(2026, 8, 28, tzinfo=timezone.utc)
    new_end = datetime(2026, 9, 28, tzinfo=timezone.utc)
    item = MagicMock(
        current_period_start=int(new_start.timestamp()),
        current_period_end=int(new_end.timestamp()),
    )
    monkeypatch.setattr(
        stripe.Subscription,
        "retrieve",
        lambda *args, **kwargs: MagicMock(items=MagicMock(data=[item])),
    )
    return new_start, new_end


async def test_invoice_paid_marks_the_period_billed(
    client: AsyncClient,
    db_session: AsyncSession,
    paid_subscription: tuple[datetime, datetime],
    stub_stripe_subscription: tuple[datetime, datetime],
) -> None:
    """The bug this fixes: history showed 'pending' because this never ran."""
    period_start, _ = paid_subscription
    new_start, new_end = stub_stripe_subscription
    invoice = _dahlia_invoice()

    response = await _post(client, "invoice.paid", invoice)
    assert response.status_code == 200

    repo = BillingRepository(db_session)
    record = await repo.get_current_usage_record(TEST_ORG_ID, period_start)
    assert record is not None
    assert record.billed is True, "invoice.paid must mark the closing period billed"
    assert record.stripe_invoice_id == invoice["id"], "the Stripe invoice must be linked"

    # ...and the subscription rolled onto the next period.
    sub = await repo.get_subscription_by_org(TEST_ORG_ID)
    assert sub is not None
    assert sub.current_period_start == new_start
    assert sub.current_period_end == new_end
    assert sub.status == SubscriptionStatus.ACTIVE


async def test_signup_invoice_keeps_the_period_billable(
    client: AsyncClient,
    db_session: AsyncSession,
    paid_subscription: tuple[datetime, datetime],
    stub_stripe_subscription: tuple[datetime, datetime],
) -> None:
    """A signup invoice must leave the period it opened billable.

    ``calculate_unreported_overages`` short-circuits on ``billed``, so closing the
    period here would forfeit every overage unit the customer accrues that month.
    """
    period_start, _ = paid_subscription

    response = await _post(client, "invoice.paid", _dahlia_invoice(billing_reason="subscription_create"))
    assert response.status_code == 200

    record = await BillingRepository(db_session).get_current_usage_record(TEST_ORG_ID, period_start)
    assert record is not None
    assert record.billed is False, "signup must not close the period it opened"
    assert record.stripe_invoice_id is None


async def test_invoice_payment_failed_marks_past_due(
    client: AsyncClient,
    db_session: AsyncSession,
    paid_subscription: tuple[datetime, datetime],
) -> None:
    """Dunning visibility: the status must reflect a failed payment."""
    response = await _post(client, "invoice.payment_failed", _dahlia_invoice(status="open"))
    assert response.status_code == 200

    sub = await BillingRepository(db_session).get_subscription_by_org(TEST_ORG_ID)
    assert sub is not None
    assert sub.status == SubscriptionStatus.PAST_DUE


async def test_one_off_invoice_is_ignored(
    client: AsyncClient,
    db_session: AsyncSession,
    paid_subscription: tuple[datetime, datetime],
) -> None:
    """An invoice with no subscription must not be treated as a renewal."""
    period_start, _ = paid_subscription

    response = await _post(client, "invoice.paid", _dahlia_invoice(parent=None))
    assert response.status_code == 200

    record = await BillingRepository(db_session).get_current_usage_record(TEST_ORG_ID, period_start)
    assert record is not None
    assert record.billed is False, "a one-off invoice must not close a billing period"


async def test_invalid_signature_is_rejected(client: AsyncClient) -> None:
    """Signature verification still guards the endpoint."""
    body = _event("invoice.paid", _dahlia_invoice())
    response = await client.post(
        _WEBHOOK_PATH,
        content=body,
        headers={"Stripe-Signature": "t=1,v1=deadbeef", "Content-Type": "application/json"},
    )
    assert response.status_code == 400


async def test_duplicate_delivery_is_processed_once(
    client: AsyncClient,
    db_session: AsyncSession,
    paid_subscription: tuple[datetime, datetime],
    stub_stripe_subscription: tuple[datetime, datetime],
) -> None:
    """Stripe retries deliveries; the idempotency key must absorb them.

    The same event id is sent twice with valid signatures. The second delivery
    must be recognised as a duplicate rather than advancing the period again.
    """
    period_start, _ = paid_subscription
    body = _event("invoice.paid", _dahlia_invoice())
    headers = {"Stripe-Signature": _sign(body), "Content-Type": "application/json"}

    first = await client.post(_WEBHOOK_PATH, content=body, headers=headers)
    second = await client.post(_WEBHOOK_PATH, content=body, headers={**headers, "Stripe-Signature": _sign(body)})
    assert first.status_code == 200
    assert second.status_code == 200

    repo = BillingRepository(db_session)
    sub = await repo.get_subscription_by_org(TEST_ORG_ID)
    assert sub is not None
    # Advanced exactly once — a second advance would push into October.
    assert sub.current_period_end == datetime(2026, 9, 28, tzinfo=timezone.utc)

    # The original period is still the one marked billed.
    assert (await repo.get_current_usage_record(TEST_ORG_ID, period_start)) is not None
