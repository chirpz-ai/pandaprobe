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
from itertools import permutations
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
import redis.asyncio as aioredis
import stripe
from httpx import AsyncClient, Response
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models import SubscriptionModel, UsageRecordModel
from app.infrastructure.db.repositories.billing_repo import BillingRepository
from app.infrastructure.redis.client import redis_pool
from app.infrastructure.redis.locks import acquire_owned_lock
from app.registry.constants import SubscriptionPlan, SubscriptionStatus
from app.registry.settings import settings
from app.services.billing_service import BillingService
from app.services.usage_service import UsageService
from app.services.billing_reporting_service import BillingReportingService
from app.infrastructure.db.repositories.billing_report_repo import BillingReportRepository

from .conftest import TEST_ORG_ID

_WEBHOOK_PATH = "/webhooks/stripe"
_STRIPE_SUB_ID = "sub_webhook_verify"


@pytest.fixture
async def redis_client():
    """Use the same isolated Redis database as webhook handlers."""
    async with aioredis.Redis(connection_pool=redis_pool) as client:
        yield client


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
        "period_start": int(datetime(2026, 7, 28, tzinfo=timezone.utc).timestamp()),
        "period_end": int(datetime(2026, 8, 28, tzinfo=timezone.utc).timestamp()),
        "parent": {
            "quote_details": None,
            "subscription_details": {"metadata": {}, "subscription": _STRIPE_SUB_ID},
            "type": "subscription_details",
        },
    }
    invoice.update(overrides)
    return invoice


@pytest.fixture
def deliver(client: AsyncClient, db_session: AsyncSession):
    """Deliver a signed event, then drop the test session's cached ORM state.

    The route commits through its own ``async_session_factory()`` session, so
    ``db_session`` never observes those writes on its own: its identity map still
    holds the instances the fixtures inserted, and the factory sets
    ``expire_on_commit=False``, so a later ``select()`` hands back those same
    objects carrying their pre-webhook values.  The staleness is selective --
    columns the fixtures set explicitly (``billed``, the period bounds, ``status``)
    read stale, while ones they left unset are populated by the query -- which is
    how an assertion on ``billed`` can fail with the ``stripe_invoice_id`` check
    beside it still passing.  Expiring here forces the next read to hit the
    database.
    """

    async def _deliver(body: bytes, *, signature: str | None = None) -> Response:
        response = await client.post(
            _WEBHOOK_PATH,
            content=body,
            headers={
                "Stripe-Signature": signature or _sign(body),
                "Content-Type": "application/json",
            },
        )
        db_session.expire_all()
        return response

    return _deliver


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
    deliver,
    db_session: AsyncSession,
    paid_subscription: tuple[datetime, datetime],
    stub_stripe_subscription: tuple[datetime, datetime],
) -> None:
    """The bug this fixes: history showed 'pending' because this never ran."""
    period_start, _ = paid_subscription
    new_start, new_end = stub_stripe_subscription
    invoice = _dahlia_invoice()

    response = await deliver(_event("invoice.paid", invoice))
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
    deliver,
    db_session: AsyncSession,
    paid_subscription: tuple[datetime, datetime],
    stub_stripe_subscription: tuple[datetime, datetime],
) -> None:
    """A signup invoice must leave the period it opened billable.

    ``calculate_unreported_overages`` short-circuits on ``billed``, so closing the
    period here would forfeit every overage unit the customer accrues that month.
    """
    period_start, _ = paid_subscription

    response = await deliver(_event("invoice.paid", _dahlia_invoice(billing_reason="subscription_create")))
    assert response.status_code == 200

    record = await BillingRepository(db_session).get_current_usage_record(TEST_ORG_ID, period_start)
    assert record is not None
    assert record.billed is False, "signup must not close the period it opened"
    assert record.stripe_invoice_id is None


async def test_invoice_payment_failed_marks_past_due(
    deliver,
    db_session: AsyncSession,
    paid_subscription: tuple[datetime, datetime],
) -> None:
    """Dunning visibility: the status must reflect a failed payment."""
    response = await deliver(_event("invoice.payment_failed", _dahlia_invoice(status="open")))
    assert response.status_code == 200

    sub = await BillingRepository(db_session).get_subscription_by_org(TEST_ORG_ID)
    assert sub is not None
    assert sub.status == SubscriptionStatus.PAST_DUE


async def test_lock_acquire_retry_still_processes_webhook(
    deliver,
    db_session: AsyncSession,
    paid_subscription: tuple[datetime, datetime],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A replay after Redis accepted the lock must still report acquisition."""
    calls = 0

    async def replayed_acquire(client, key: str, token: str, *, ttl: int) -> bool:
        nonlocal calls
        calls += 1
        assert await acquire_owned_lock(client, key, token, ttl=ttl) is True
        return await acquire_owned_lock(client, key, token, ttl=ttl)

    monkeypatch.setattr("app.api.v1.routes.webhooks.acquire_owned_lock", replayed_acquire)

    response = await deliver(_event("invoice.payment_failed", _dahlia_invoice(status="open")))
    assert response.status_code == 200
    assert calls == 1

    sub = await BillingRepository(db_session).get_subscription_by_org(TEST_ORG_ID)
    assert sub is not None
    assert sub.status == SubscriptionStatus.PAST_DUE


async def test_one_off_invoice_is_ignored(
    deliver,
    db_session: AsyncSession,
    paid_subscription: tuple[datetime, datetime],
) -> None:
    """An invoice with no subscription must not be treated as a renewal."""
    period_start, _ = paid_subscription

    response = await deliver(_event("invoice.paid", _dahlia_invoice(parent=None)))
    assert response.status_code == 200

    record = await BillingRepository(db_session).get_current_usage_record(TEST_ORG_ID, period_start)
    assert record is not None
    assert record.billed is False, "a one-off invoice must not close a billing period"


async def test_invalid_signature_is_rejected(deliver) -> None:
    """Signature verification still guards the endpoint."""
    response = await deliver(_event("invoice.paid", _dahlia_invoice()), signature="t=1,v1=deadbeef")
    assert response.status_code == 400


async def test_duplicate_delivery_is_processed_once(
    deliver,
    db_session: AsyncSession,
    paid_subscription: tuple[datetime, datetime],
    stub_stripe_subscription: tuple[datetime, datetime],
) -> None:
    """Stripe retries deliveries; the idempotency key must absorb them.

    The same event id is sent twice, each freshly signed. The second delivery must
    be recognised as a duplicate rather than advancing the period again.
    """
    period_start, _ = paid_subscription
    body = _event("invoice.paid", _dahlia_invoice())

    first = await deliver(body)
    second = await deliver(body)
    assert first.status_code == 200
    assert second.status_code == 200

    repo = BillingRepository(db_session)
    sub = await repo.get_subscription_by_org(TEST_ORG_ID)
    assert sub is not None
    # Advanced exactly once — a second advance would push into October.
    assert sub.current_period_end == datetime(2026, 9, 28, tzinfo=timezone.utc)

    # The original period is still the one marked billed.
    assert (await repo.get_current_usage_record(TEST_ORG_ID, period_start)) is not None


def _subscription_updated(start: datetime, end: datetime) -> dict:
    return {
        "id": _STRIPE_SUB_ID,
        "object": "subscription",
        "status": "active",
        "items": {
            "data": [{"current_period_start": int(start.timestamp()), "current_period_end": int(end.timestamp())}]
        },
    }


@pytest.mark.parametrize(
    "order", list(permutations(["invoice.created", "invoice.paid", "customer.subscription.updated"]))
)
async def test_renewal_event_order_never_closes_new_month(
    deliver, db_session, paid_subscription, stub_stripe_subscription, order
):
    old_start, _ = paid_subscription
    new_start, new_end = stub_stripe_subscription
    repo = BillingRepository(db_session)
    # The five-minute sync may already have created the next month's row.
    await repo.get_or_create_usage_record(TEST_ORG_ID, new_start, new_end)
    await db_session.commit()
    invoice = _dahlia_invoice()
    for event_type in order:
        obj = _subscription_updated(new_start, new_end) if event_type.startswith("customer.") else invoice
        assert (await deliver(_event(event_type, obj))).status_code == 200
    old = await repo.get_current_usage_record(TEST_ORG_ID, old_start)
    new = await repo.get_current_usage_record(TEST_ORG_ID, new_start)
    assert old.billed and old.stripe_invoice_id == invoice["id"]
    assert not new.billed and new.stripe_invoice_id is None


async def test_renewal_reports_old_redis_counters_to_exact_draft_once(
    deliver, db_session, redis_client, paid_subscription, stub_stripe_subscription, monkeypatch
):
    old_start, _ = paid_subscription
    new_start, new_end = stub_stripe_subscription
    assert (
        await deliver(_event("customer.subscription.updated", _subscription_updated(new_start, new_end)))
    ).status_code == 200
    await redis_client.hset(UsageService._usage_key(TEST_ORG_ID, old_start), mapping={"traces": 6000})
    await redis_client.hset(UsageService._usage_key(TEST_ORG_ID, new_start), mapping={"traces": 9000})
    create_item = MagicMock(return_value=MagicMock(id="ii_draft"))
    monkeypatch.setattr(stripe.InvoiceItem, "create", create_item)
    monkeypatch.setattr(stripe.Invoice, "retrieve", lambda *a, **k: MagicMock(status="draft"))
    invoice = _dahlia_invoice(status="draft")
    for _ in range(2):  # distinct event IDs, not just the route's duplicate filter
        assert (await deliver(_event("invoice.created", invoice))).status_code == 200
    assert create_item.call_count == 1
    assert create_item.call_args.kwargs["invoice"] == invoice["id"]
    assert create_item.call_args.kwargs["amount"] == 400
    assert create_item.call_args.kwargs["period"]["start"] == int(old_start.timestamp())
    assert (await deliver(_event("invoice.paid", {**invoice, "status": "paid"}))).status_code == 200
    repo = BillingRepository(db_session)
    old = await repo.get_current_usage_record(TEST_ORG_ID, old_start)
    assert old.trace_count == old.reported_trace_count == 6000
    assert old.billed and old.stripe_invoice_id == invoice["id"]
    # New-period reporting must remain enabled after closing the previous month.
    await UsageService(redis_client, db_session).sync_to_database(TEST_ORG_ID)
    remaining = await BillingService(db_session).calculate_unreported_overages(TEST_ORG_ID)
    assert remaining.trace_overage == 4000


@pytest.mark.parametrize("event_type", ["invoice.created", "invoice.paid"])
async def test_late_invoice_saves_carryover_instead_of_failing(
    deliver, db_session, paid_subscription, stub_stripe_subscription, monkeypatch, event_type
):
    old_start, old_end = paid_subscription
    repo = BillingRepository(db_session)
    await repo.upsert_usage_counters(TEST_ORG_ID, old_start, old_end, trace_count=6000)
    await db_session.commit()
    create_item = MagicMock(return_value=MagicMock(id="ii_carryover"))
    monkeypatch.setattr(stripe.InvoiceItem, "create", create_item)
    monkeypatch.setattr(stripe.Invoice, "retrieve", lambda *a, **k: MagicMock(status="paid"))
    # Even an old invoice.created payload still claiming draft must check live state.
    response = await deliver(_event(event_type, _dahlia_invoice(status="draft")))
    assert response.status_code == 200
    old = await repo.get_current_usage_record(TEST_ORG_ID, old_start)
    assert old.billed is (event_type == "invoice.paid")
    for report_id in await BillingReportRepository(db_session).pending_ids():
        assert await BillingReportingService(db_session).deliver(report_id)
    assert create_item.call_count == 1
    assert "invoice" not in create_item.call_args.kwargs
    assert create_item.call_args.kwargs["subscription"] == _STRIPE_SUB_ID
    old = await repo.get_current_usage_record(TEST_ORG_ID, old_start)
    assert old.reported_trace_count == 6000


@pytest.mark.parametrize("event_type", ["invoice.created", "invoice.paid"])
async def test_busy_overage_lock_allows_same_event_retry(
    deliver, db_session, redis_client, paid_subscription, stub_stripe_subscription, event_type
):
    from app.registry.constants import OVERAGE_LOCK_PREFIX

    key = f"{OVERAGE_LOCK_PREFIX}{TEST_ORG_ID}"
    await redis_client.set(key, "other-owner", ex=60)
    body = _event(event_type, _dahlia_invoice())
    assert (await deliver(body)).status_code == 500
    old = await BillingRepository(db_session).get_current_usage_record(TEST_ORG_ID, paid_subscription[0])
    assert not old.billed
    assert await redis_client.get(key) == "other-owner"
    await redis_client.delete(key)
    assert (await deliver(body)).status_code == 200


async def test_delayed_subscription_event_cannot_rewind_period(
    deliver, db_session, paid_subscription, stub_stripe_subscription
):
    new_start, new_end = stub_stripe_subscription
    for start, end in [stub_stripe_subscription, paid_subscription]:
        assert (
            await deliver(_event("customer.subscription.updated", _subscription_updated(start, end)))
        ).status_code == 200
    sub = await BillingRepository(db_session).get_subscription_by_org(TEST_ORG_ID)
    assert (sub.current_period_start, sub.current_period_end) == (new_start, new_end)


async def test_partial_stripe_failure_retries_same_invoice_and_idempotency_keys(
    deliver, db_session, paid_subscription, monkeypatch
):
    from app.registry.exceptions import PandaProbeError

    start, end = paid_subscription
    repo = BillingRepository(db_session)
    await repo.upsert_usage_counters(TEST_ORG_ID, start, end, trace_count=6000, trace_eval_count=6000)
    await db_session.commit()
    create_item = MagicMock(
        side_effect=[MagicMock(id="ii_first"), PandaProbeError("simulated Stripe failure"), MagicMock(id="ii_second")]
    )
    monkeypatch.setattr(stripe.InvoiceItem, "create", create_item)
    monkeypatch.setattr(stripe.Invoice, "retrieve", lambda *a, **k: MagicMock(status="draft"))
    invoice = _dahlia_invoice(status="draft")
    body = _event("invoice.created", invoice)
    assert (await deliver(body)).status_code == 200
    old = await repo.get_current_usage_record(TEST_ORG_ID, start)
    assert old.reported_trace_count == old.reported_trace_eval_count == 0
    assert not old.billed
    assert (await deliver(body)).status_code == 200
    for report_id in await BillingReportRepository(db_session).pending_ids():
        assert await BillingReportingService(db_session).deliver(report_id)
    calls = create_item.call_args_list
    assert len(calls) == 3 and calls[1] == calls[2]
    assert all(call.kwargs["invoice"] == invoice["id"] for call in calls)
    old = await repo.get_current_usage_record(TEST_ORG_ID, start)
    assert old.reported_trace_count == old.reported_trace_eval_count == 6000
