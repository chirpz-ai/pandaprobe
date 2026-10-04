"""Durable carryover: real transactions/Redis, simulated Stripe failure boundaries."""

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
import stripe
from sqlalchemy import select, update

from app.infrastructure.db.engine import async_session_factory
from app.infrastructure.db.models import BillingReportModel
from app.infrastructure.db.repositories.billing_repo import BillingRepository
from app.infrastructure.db.repositories.billing_report_repo import BillingReportRepository
from app.infrastructure.queue.tasks import _check_closed_billing_period, _dispatch_billing_reports
from app.services.billing_reporting_service import BillingReportingService
from app.services.billing_service import BillingService
from app.services.usage_service import UsageService

from .conftest import TEST_ORG_ID
from . import test_stripe_webhooks as webhook_helpers
from .test_stripe_webhooks import _dahlia_invoice, _event

# Reuse the same signed-HTTP fixtures without duplicating their setup/cleanup.
deliver = webhook_helpers.deliver
paid_subscription = webhook_helpers.paid_subscription
redis_client = webhook_helpers.redis_client
stub_stripe_subscription = webhook_helpers.stub_stripe_subscription
_drop_pooled_redis_connections = webhook_helpers._drop_pooled_redis_connections


@pytest.fixture
def fake_stripe(monkeypatch):
    """Simulate cached requests, recording immutable params and resulting items."""
    accepted = {}
    calls = []

    def create(**params):
        calls.append(deepcopy(params))
        key = params["idempotency_key"]
        if key in accepted:
            assert accepted[key][0] == params
            return accepted[key][1]
        item = SimpleNamespace(
            id=f"ii_{len(accepted)}", metadata=params["metadata"], amount=params["amount"], currency="usd"
        )
        accepted[key] = (deepcopy(params), item)
        return item

    monkeypatch.setattr(stripe.InvoiceItem, "create", create)
    monkeypatch.setattr(
        stripe.InvoiceItem,
        "list",
        lambda **kw: SimpleNamespace(auto_paging_iter=lambda: iter([v[1] for v in accepted.values()])),
    )
    monkeypatch.setattr(stripe.Invoice, "retrieve", lambda *a, **kw: SimpleNamespace(status="draft"))
    return SimpleNamespace(create=create, accepted=accepted, calls=calls)


async def _stage(session, bounds, *, count=6000, invoice=None):
    repo = BillingRepository(session)
    await repo.upsert_usage_counters(TEST_ORG_ID, *bounds, trace_count=count)
    sub = await repo.get_subscription_by_org(TEST_ORG_ID)
    report = await BillingReportingService(session).stage(sub, bounds[0], invoice_id=invoice)
    await session.commit()
    return report


async def _reports(session):
    session.expire_all()
    return list((await session.execute(select(BillingReportModel).order_by(BillingReportModel.created_at))).scalars())


async def test_paid_renewal_closes_with_trailing_usage_even_when_stripe_delivery_is_down(
    deliver, db_session, redis_client, paid_subscription, stub_stripe_subscription, fake_stripe, monkeypatch
):
    start, end = paid_subscription
    key = UsageService._usage_key(TEST_ORG_ID, start)
    await redis_client.hset(key, mapping={"traces": 6000})
    invoice = _dahlia_invoice()
    assert (await deliver(_event("invoice.created", invoice))).status_code == 200
    assert len(fake_stripe.accepted) == 1
    # 6,250 more units arrive after the draft capture: exactly $25 to carry over.
    await redis_client.hset(key, mapping={"traces": 12250})
    monkeypatch.setattr(stripe.InvoiceItem, "create", MagicMock(side_effect=stripe.APIConnectionError("offline")))
    for _ in range(2):  # distinct event IDs cannot reserve the same remainder twice
        assert (await deliver(_event("invoice.paid", invoice))).status_code == 200
    repo = BillingRepository(db_session)
    old = await repo.get_current_usage_record(TEST_ORG_ID, start)
    new = await repo.get_current_usage_record(TEST_ORG_ID, stub_stripe_subscription[0])
    sub = await repo.get_subscription_by_org(TEST_ORG_ID)
    assert old.billed and old.reported_trace_count == 6000
    assert not new.billed and new.trace_count == 0
    assert sub.current_period_start == stub_stripe_subscription[0]
    pending = await BillingReportRepository(db_session).pending_ids()
    assert len(pending) == 1
    assert not await BillingReportingService(db_session).deliver_safely(pending[0])
    reports = await _reports(db_session)
    carryover = next(r for r in reports if r.status == "pending")
    assert carryover.requests["traces"]["amount"] == 2500
    assert "invoice" not in carryover.requests["traces"]
    assert carryover.requests["traces"]["period"] == {"start": int(start.timestamp()), "end": int(end.timestamp())}
    monkeypatch.setattr(stripe.InvoiceItem, "create", fake_stripe.create)
    assert await BillingReportingService(db_session).deliver(pending[0])
    old = await repo.get_current_usage_record(TEST_ORG_ID, start)
    assert old.billed and old.reported_trace_count == 12250
    assert len(fake_stripe.accepted) == 2


async def test_crash_after_stripe_acceptance_reuses_frozen_request(
    db_session, paid_subscription, fake_stripe, monkeypatch
):
    report = await _stage(db_session, paid_subscription)
    crashed = False

    def uncertain(**params):
        nonlocal crashed
        result = fake_stripe.create(**params)
        if not crashed:
            crashed = True
            raise stripe.APIConnectionError("response lost after Stripe accepted")
        return result

    monkeypatch.setattr(stripe.InvoiceItem, "create", uncertain)
    service = BillingReportingService(db_session)
    assert not await service.deliver_safely(report.id)
    assert await service.deliver(report.id)
    assert len(fake_stripe.accepted) == 1
    assert fake_stripe.calls[0] == fake_stripe.calls[1]


async def test_expired_idempotency_recovers_known_item_or_requires_review(db_session, paid_subscription, fake_stripe):
    report = await _stage(db_session, paid_subscription)
    attempted = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    await BillingReportRepository(db_session).update(report.id, attempted_at={"traces": attempted})
    await db_session.commit()
    # The request may have reached Stripe; no match is not permission to charge again.
    service = BillingReportingService(db_session)
    assert not await service.deliver(report.id)
    assert (await _reports(db_session))[0].status == "needs_review"
    assert not fake_stripe.calls
    # Once matching evidence exists, a reviewed retry can recover it without creation.
    fake_stripe.create(**report.requests["traces"])
    await BillingReportRepository(db_session).update(report.id, status="pending")
    await db_session.commit()
    assert await service.deliver(report.id)
    assert len(fake_stripe.calls) == 1


async def test_usage_growth_during_failure_reserves_only_the_additional_delta(
    db_session, paid_subscription, fake_stripe
):
    first = await _stage(db_session, paid_subscription, count=6000)
    second = await _stage(db_session, paid_subscription, count=6500)
    assert first.requests["traces"]["amount"] == 400
    assert second.requests["traces"]["amount"] == 200
    assert await _stage(db_session, paid_subscription, count=6500) is None
    # Deliver out of order: the older unresolved obligation must not be hidden.
    service = BillingReportingService(db_session)
    assert await service.deliver(second.id)
    repo = BillingRepository(db_session)
    assert (await repo.get_current_usage_record(TEST_ORG_ID, paid_subscription[0])).reported_trace_count == 0
    assert await service.deliver(first.id)
    assert (await repo.get_current_usage_record(TEST_ORG_ID, paid_subscription[0])).reported_trace_count == 6500
    assert sum(v[1].amount for v in fake_stripe.accepted.values()) == 600


async def test_draft_attempt_then_paid_webhook_does_not_duplicate_reserved_charge(
    deliver, db_session, paid_subscription, stub_stripe_subscription, fake_stripe, monkeypatch
):
    report = await _stage(db_session, paid_subscription, invoice="in_draft")

    def uncertain(**params):
        fake_stripe.create(**params)
        raise stripe.APIConnectionError("response lost")

    monkeypatch.setattr(stripe.InvoiceItem, "create", uncertain)
    assert not await BillingReportingService(db_session).deliver_safely(report.id)
    assert (await deliver(_event("invoice.paid", _dahlia_invoice(id="in_draft")))).status_code == 200
    assert len(await BillingReportRepository(db_session).pending_ids()) == 1
    monkeypatch.setattr(stripe.InvoiceItem, "create", fake_stripe.create)
    monkeypatch.setattr(stripe.Invoice, "retrieve", lambda *a, **kw: SimpleNamespace(status="paid"))
    assert await BillingReportingService(db_session).deliver(report.id)
    assert len(fake_stripe.accepted) == 1
    assert fake_stripe.calls[0] == fake_stripe.calls[1]


async def test_finalization_race_definitive_rejection_becomes_carryover(
    db_session, paid_subscription, fake_stripe, monkeypatch
):
    report = await _stage(db_session, paid_subscription, invoice="in_race")
    statuses = iter(["draft", "paid"])
    monkeypatch.setattr(stripe.Invoice, "retrieve", lambda *a, **kw: SimpleNamespace(status=next(statuses)))

    def create(**params):
        if "invoice" in params:
            raise stripe.InvalidRequestError(
                "Invoice is no longer editable", param="invoice", code="invoice_not_editable"
            )
        return fake_stripe.create(**params)

    monkeypatch.setattr(stripe.InvoiceItem, "create", create)
    assert await BillingReportingService(db_session).deliver(report.id)
    assert len(fake_stripe.accepted) == 1
    assert fake_stripe.calls[0]["idempotency_key"].endswith(":carryover")
    assert "invoice" not in fake_stripe.calls[0]


async def test_late_counters_after_closure_are_captured_without_reopening_or_rebilling_history(
    deliver, db_session, redis_client, paid_subscription, stub_stripe_subscription, fake_stripe
):
    start, end = paid_subscription
    invoice = _dahlia_invoice()
    assert (await deliver(_event("invoice.paid", invoice))).status_code == 200
    marker = (await _reports(db_session))[0]
    assert marker.requests == {} and marker.status == "reported"
    marker_id = str(marker.id)
    await db_session.commit()
    await redis_client.hset(UsageService._usage_key(TEST_ORG_ID, start), mapping={"traces": 7000})
    for _ in range(2):
        await _check_closed_billing_period(str(TEST_ORG_ID), start.isoformat(), end.isoformat(), marker_id)
    reports = await _reports(db_session)
    assert len(reports) == 2
    assert next(r for r in reports if r.requests).requests["traces"]["amount"] == 800
    old = await BillingRepository(db_session).get_current_usage_record(TEST_ORG_ID, start)
    assert old.billed and old.trace_count == 7000
    assert not fake_stripe.calls


async def test_canceled_subscription_holds_carryover_for_review_not_another_subscription(
    db_session, paid_subscription, fake_stripe
):
    report = await _stage(db_session, paid_subscription)
    await BillingRepository(db_session).update_subscription(TEST_ORG_ID, stripe_subscription_id="sub_replacement")
    await db_session.commit()
    assert not await BillingReportingService(db_session).deliver(report.id)
    assert (await _reports(db_session))[0].status == "needs_review"
    assert not fake_stripe.calls


async def test_reservation_and_period_close_roll_back_together(db_session, paid_subscription):
    repo = BillingRepository(db_session)
    await repo.upsert_usage_counters(TEST_ORG_ID, *paid_subscription, trace_count=6000)
    await db_session.commit()
    sub = await repo.get_subscription_by_org(TEST_ORG_ID)
    await BillingReportingService(db_session).stage(sub, paid_subscription[0], closing_invoice_id="in_atomic")
    await repo.mark_billed(TEST_ORG_ID, paid_subscription[0], "in_atomic")
    await db_session.rollback()
    assert not await _reports(db_session)
    assert not (await repo.get_current_usage_record(TEST_ORG_ID, paid_subscription[0])).billed


async def test_concurrent_reservations_do_not_overlap(db_session, paid_subscription):
    repo = BillingRepository(db_session)
    await repo.upsert_usage_counters(TEST_ORG_ID, *paid_subscription, trace_count=6000)
    await db_session.commit()

    async def stage():
        async with async_session_factory() as session:
            sub = await BillingRepository(session).get_subscription_by_org(TEST_ORG_ID)
            report = await BillingReportingService(session).stage(sub, paid_subscription[0])
            await session.commit()
            return report

    reports = await asyncio.gather(stage(), stage())
    assert sum(r is not None for r in reports) == 1


async def test_locked_delivery_is_skipped_by_other_workers(db_session, paid_subscription, fake_stripe):
    report = await _stage(db_session, paid_subscription)
    await BillingReportRepository(db_session).lock_report(report.id)
    async with async_session_factory() as other:
        assert not await BillingReportingService(other).deliver(report.id)
    assert not fake_stripe.calls
    await db_session.rollback()
    assert await BillingReportingService(db_session).deliver(report.id)


async def test_reserved_period_keeps_original_pricing_after_plan_change(db_session, paid_subscription):
    first = await _stage(db_session, paid_subscription, count=6000)
    await BillingRepository(db_session).update_subscription(TEST_ORG_ID, plan="STARTUP")
    await db_session.commit()
    second = await _stage(db_session, paid_subscription, count=7000)
    assert second.pricing == first.pricing
    assert second.requests["traces"]["amount"] == 400


async def test_dispatcher_recovers_intents_without_requiring_active_subscription(
    db_session, paid_subscription, monkeypatch
):
    from app.infrastructure.queue import tasks

    report = await _stage(db_session, paid_subscription)
    await BillingRepository(db_session).update_subscription(TEST_ORG_ID, status="CANCELED")
    await db_session.commit()
    delivery = MagicMock()
    followup = MagicMock()
    monkeypatch.setattr(tasks.deliver_billing_report, "delay", delivery)
    monkeypatch.setattr(tasks.check_closed_billing_period, "delay", followup)
    result = await _dispatch_billing_reports()
    assert result == {"dispatched": 1}
    delivery.assert_called_once_with(str(report.id))
    followup.assert_not_called()


async def test_legacy_history_is_not_automatically_enrolled(db_session, paid_subscription):
    repo = BillingRepository(db_session)
    await repo.mark_billed(TEST_ORG_ID, paid_subscription[0], "in_historical")
    await db_session.commit()
    outbox = BillingReportRepository(db_session)
    assert await outbox.recent_closures(datetime.now(timezone.utc) - timedelta(days=7)) == []


async def test_late_usage_checks_are_bounded_but_delivery_obligations_do_not_expire(db_session, paid_subscription):
    repo = BillingRepository(db_session)
    await repo.upsert_usage_counters(TEST_ORG_ID, *paid_subscription, trace_count=6000)
    sub = await repo.get_subscription_by_org(TEST_ORG_ID)
    report = await BillingReportingService(db_session).stage(sub, paid_subscription[0], closing_invoice_id="in_old")
    await BillingReportRepository(db_session).update(
        report.id, created_at=datetime.now(timezone.utc) - timedelta(days=8)
    )
    await db_session.commit()
    outbox = BillingReportRepository(db_session)
    assert await outbox.recent_closures(datetime.now(timezone.utc) - timedelta(days=7)) == []
    assert await outbox.pending_ids() == [report.id]


async def test_expired_recovery_scan_is_bounded(db_session, paid_subscription, fake_stripe, monkeypatch):
    report = await _stage(db_session, paid_subscription)
    await BillingReportRepository(db_session).update(
        report.id, attempted_at={"traces": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()}
    )
    await db_session.commit()
    scanned = 0

    def items():
        nonlocal scanned
        for _ in range(2000):
            scanned += 1
            yield SimpleNamespace(metadata={})

    monkeypatch.setattr(stripe.InvoiceItem, "list", lambda **kw: SimpleNamespace(auto_paging_iter=items))
    assert not await BillingReportingService(db_session).deliver(report.id)
    assert scanned == 1000
    assert (await _reports(db_session))[0].status == "needs_review"
    assert not fake_stripe.calls


@pytest.mark.parametrize("invoice", [None, "in_draft"])
async def test_reserved_request_uses_supported_stripe_create_parameters(db_session, paid_subscription, invoice):
    from stripe.params import InvoiceItemCreateParams

    report = await _stage(db_session, paid_subscription, invoice=invoice)
    params = report.requests["traces"]
    # idempotency_key is an SDK request option, not a form-body parameter.
    assert set(params) - {"idempotency_key"} <= InvoiceItemCreateParams.__annotations__.keys()
    assert params["subscription"] == report.stripe_subscription_id
    assert params.get("invoice") == invoice


async def test_core_update_advances_report_timestamp(db_session, paid_subscription):
    report = await _stage(db_session, paid_subscription)
    repo = BillingReportRepository(db_session)
    old = datetime.now(timezone.utc) - timedelta(days=1)
    await repo.update(report.id, updated_at=old)
    await db_session.commit()

    before = datetime.now(timezone.utc)
    await repo.update(report.id, last_error="temporary Stripe failure")
    await db_session.commit()
    stored = (await _reports(db_session))[0]
    assert stored.updated_at >= before
    assert stored.updated_at > old


async def test_failed_batch_yields_to_newer_pending_reports(db_session, paid_subscription, monkeypatch):
    """The first 200 failures must not monopolize the next dispatch batch."""
    from uuid import uuid4

    first = await _stage(db_session, paid_subscription)
    repo = BillingReportRepository(db_session)
    old = datetime.now(timezone.utc) - timedelta(days=1)
    await repo.update(first.id, updated_at=old)
    for index in range(200):
        await repo.create(
            id=uuid4(),
            usage_record_id=first.usage_record_id,
            stripe_customer_id=first.stripe_customer_id,
            stripe_subscription_id=first.stripe_subscription_id,
            snapshot_trace_count=first.snapshot_trace_count,
            snapshot_trace_eval_count=first.snapshot_trace_eval_count,
            snapshot_session_eval_count=first.snapshot_session_eval_count,
            pricing=first.pricing,
            requests=first.requests,
            updated_at=old + timedelta(seconds=index + 1),
        )
    await db_session.commit()
    original = await repo.pending_ids()
    all_ids = await repo.pending_ids(limit=201)
    assert len(original) == 200
    waiting = all_ids[-1]
    assert waiting not in original

    # Fail before the first create attempt, exercising deliver_safely's Core
    # error update rather than relying on another update to refresh the clock.
    async def fail_delivery(self, report_id):
        raise RuntimeError("Stripe unavailable")

    monkeypatch.setattr(BillingReportingService, "deliver", fail_delivery)
    service = BillingReportingService(db_session)
    for report_id in original:
        assert not await service.deliver_safely(report_id)
    assert (await repo.pending_ids())[0] == waiting
