import json
from decimal import Decimal
from unittest.mock import patch

import pytest
import redis.asyncio as aioredis
from httpx import AsyncClient
from sqlalchemy import delete

from app.core.billing.plans import OVERAGE_UNIT_PRICE
from app.infrastructure.db.models import SubscriptionModel, UsageRecordModel
from app.infrastructure.db.repositories.billing_repo import BillingRepository
from app.registry.constants import SubscriptionPlan, SubscriptionStatus, UsageCategory
from app.registry.exceptions import QuotaExceededError
from app.registry.settings import settings
from app.services.billing_service import BillingService
from app.services.usage_service import UsageService

from .conftest import TEST_ORG_ID
from .factories import _serialize_payload, build_trace_payload


@pytest.fixture(autouse=True)
async def _clear_seeded_subscription_for_usage_tests(db_session):
    await db_session.execute(delete(UsageRecordModel).where(UsageRecordModel.org_id == TEST_ORG_ID))
    await db_session.execute(delete(SubscriptionModel).where(SubscriptionModel.org_id == TEST_ORG_ID))
    await db_session.commit()
    yield


@pytest.fixture
async def redis_client():
    client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    yield client
    await client.flushdb()
    await client.aclose()


async def test_check_and_increment_increments_for_paid_plan(db_session, redis_client):
    repo = BillingRepository(db_session)
    await repo.create_subscription(
        TEST_ORG_ID,
        plan=SubscriptionPlan.PRO,
        stripe_subscription_id="sub_paid",
    )
    await db_session.commit()
    svc = UsageService(redis_client, db_session)
    n = await svc.check_and_increment(TEST_ORG_ID, UsageCategory.TRACES)
    assert n == 1


async def test_check_and_increment_hobby_raises_when_trace_limit_reached(db_session, redis_client):
    repo = BillingRepository(db_session)
    sub = await repo.create_subscription(TEST_ORG_ID)
    await db_session.commit()
    svc = UsageService(redis_client, db_session)
    key = f"pp:usage:{TEST_ORG_ID}:{sub.current_period_start.strftime('%Y-%m-%d')}"
    await redis_client.hset(key, "traces", "100")
    with pytest.raises(QuotaExceededError):
        await svc.check_and_increment(TEST_ORG_ID, UsageCategory.TRACES)


async def test_check_and_increment_paid_plan_not_blocked_above_base_trace_limit(db_session, redis_client):
    repo = BillingRepository(db_session)
    sub = await repo.create_subscription(
        TEST_ORG_ID,
        plan=SubscriptionPlan.PRO,
        stripe_subscription_id="sub_pro2",
    )
    await db_session.commit()
    svc = UsageService(redis_client, db_session)
    key = f"pp:usage:{TEST_ORG_ID}:{sub.current_period_start.strftime('%Y-%m-%d')}"
    await redis_client.hset(key, "traces", "10000")
    n = await svc.check_and_increment(TEST_ORG_ID, UsageCategory.TRACES)
    assert n == 10001


async def test_get_current_usage_returns_redis_counters(db_session, redis_client):
    repo = BillingRepository(db_session)
    sub = await repo.create_subscription(TEST_ORG_ID, plan=SubscriptionPlan.PRO, stripe_subscription_id="sub_x")
    await db_session.commit()
    key = f"pp:usage:{TEST_ORG_ID}:{sub.current_period_start.strftime('%Y-%m-%d')}"
    await redis_client.hset(
        key,
        mapping={"traces": "4", "trace_evals": "1", "session_evals": "2"},
    )
    svc = UsageService(redis_client, db_session)
    summary = await svc.get_current_usage(TEST_ORG_ID)
    assert summary.traces == 4
    assert summary.trace_evals == 1
    assert summary.session_evals == 2


async def test_sync_to_database_persists_redis_counters(db_session, redis_client):
    repo = BillingRepository(db_session)
    sub = await repo.create_subscription(TEST_ORG_ID, plan=SubscriptionPlan.PRO, stripe_subscription_id="sub_sync")
    await db_session.commit()
    key = f"pp:usage:{TEST_ORG_ID}:{sub.current_period_start.strftime('%Y-%m-%d')}"
    await redis_client.hset(
        key,
        mapping={"traces": "9", "trace_evals": "8", "session_evals": "7"},
    )
    svc = UsageService(redis_client, db_session)
    await svc.sync_to_database(TEST_ORG_ID)
    await db_session.commit()
    row = await repo.get_current_usage_record(TEST_ORG_ID, sub.current_period_start)
    assert row is not None
    assert row.trace_count == 9
    assert row.trace_eval_count == 8
    assert row.session_eval_count == 7


async def test_invalidate_subscription_cache_removes_cache_key(db_session, redis_client):
    repo = BillingRepository(db_session)
    await repo.create_subscription(TEST_ORG_ID)
    await db_session.commit()
    svc = UsageService(redis_client, db_session)
    await svc.get_current_usage(TEST_ORG_ID)
    cache_key = f"pp:sub:{TEST_ORG_ID}"
    assert await redis_client.get(cache_key) is not None
    await svc.invalidate_subscription_cache(TEST_ORG_ID)
    assert await redis_client.get(cache_key) is None


async def test_subscription_cache_populated_after_usage_lookup(db_session, redis_client):
    repo = BillingRepository(db_session)
    await repo.create_subscription(TEST_ORG_ID)
    await db_session.commit()
    svc = UsageService(redis_client, db_session)
    await svc.get_current_usage(TEST_ORG_ID)
    raw = await redis_client.get(f"pp:sub:{TEST_ORG_ID}")
    assert raw is not None
    data = json.loads(raw)
    assert data["org_id"] == str(TEST_ORG_ID)
    await svc.get_current_usage(TEST_ORG_ID)
    assert await redis_client.get(f"pp:sub:{TEST_ORG_ID}") is not None


async def test_post_traces_succeeds_when_under_quota(client: AsyncClient, db_session, redis_client):
    repo = BillingRepository(db_session)
    await repo.create_subscription(TEST_ORG_ID)
    await db_session.commit()
    payload = _serialize_payload(build_trace_payload(name="under-quota"))
    resp = await client.post("/traces", json=payload)
    assert resp.status_code == 202


async def test_post_traces_returns_429_when_hobby_trace_limit_reached(client: AsyncClient, db_session, redis_client):
    repo = BillingRepository(db_session)
    sub = await repo.create_subscription(TEST_ORG_ID)
    await db_session.commit()
    key = f"pp:usage:{TEST_ORG_ID}:{sub.current_period_start.strftime('%Y-%m-%d')}"
    await redis_client.hset(key, "traces", "100")
    payload = _serialize_payload(build_trace_payload(name="over-quota"))
    resp = await client.post("/traces", json=payload)
    assert resp.status_code == 429


# ---------------------------------------------------------------------------
# Edge case: HOBBY at exact limit boundary
# ---------------------------------------------------------------------------


async def test_hobby_trace_at_99_allows_one_more(db_session, redis_client):
    """At 99/100, one more should succeed (reaching exactly the limit)."""
    repo = BillingRepository(db_session)
    sub = await repo.create_subscription(TEST_ORG_ID)
    await db_session.commit()
    key = f"pp:usage:{TEST_ORG_ID}:{sub.current_period_start.strftime('%Y-%m-%d')}"
    await redis_client.hset(key, "traces", "99")
    svc = UsageService(redis_client, db_session)
    n = await svc.check_and_increment(TEST_ORG_ID, UsageCategory.TRACES)
    assert n == 100


async def test_hobby_trace_at_100_blocks_next(db_session, redis_client):
    """At exactly the limit, the next request must be rejected."""
    repo = BillingRepository(db_session)
    sub = await repo.create_subscription(TEST_ORG_ID)
    await db_session.commit()
    key = f"pp:usage:{TEST_ORG_ID}:{sub.current_period_start.strftime('%Y-%m-%d')}"
    await redis_client.hset(key, "traces", "100")
    svc = UsageService(redis_client, db_session)
    with pytest.raises(QuotaExceededError):
        await svc.check_and_increment(TEST_ORG_ID, UsageCategory.TRACES)


async def test_hobby_bulk_increment_crossing_limit_rejected_atomically(db_session, redis_client):
    """A bulk increment that would cross the limit is rejected and counter stays unchanged."""
    repo = BillingRepository(db_session)
    sub = await repo.create_subscription(TEST_ORG_ID)
    await db_session.commit()
    key = f"pp:usage:{TEST_ORG_ID}:{sub.current_period_start.strftime('%Y-%m-%d')}"
    await redis_client.hset(key, "trace_evals", "98")
    svc = UsageService(redis_client, db_session)
    with pytest.raises(QuotaExceededError):
        await svc.check_and_increment(TEST_ORG_ID, UsageCategory.TRACE_EVALS, count=5)
    raw_val = await redis_client.hget(key, "trace_evals")
    assert int(raw_val) == 98, "Counter must be rolled back after rejected bulk increment"


async def test_hobby_session_eval_limit_enforced(db_session, redis_client):
    """HOBBY session eval limit (10) is enforced correctly."""
    repo = BillingRepository(db_session)
    sub = await repo.create_subscription(TEST_ORG_ID)
    await db_session.commit()
    key = f"pp:usage:{TEST_ORG_ID}:{sub.current_period_start.strftime('%Y-%m-%d')}"
    await redis_client.hset(key, "session_evals", "10")
    svc = UsageService(redis_client, db_session)
    with pytest.raises(QuotaExceededError):
        await svc.check_and_increment(TEST_ORG_ID, UsageCategory.SESSION_EVALS)


async def test_paid_plan_above_base_limit_allows_increment(db_session, redis_client):
    """PRO plan should not block even when well above base limit (pay-as-you-go)."""
    repo = BillingRepository(db_session)
    sub = await repo.create_subscription(
        TEST_ORG_ID,
        plan=SubscriptionPlan.PRO,
        stripe_subscription_id="sub_payg",
    )
    await db_session.commit()
    key = f"pp:usage:{TEST_ORG_ID}:{sub.current_period_start.strftime('%Y-%m-%d')}"
    await redis_client.hset(key, "trace_evals", "999999")
    svc = UsageService(redis_client, db_session)
    n = await svc.check_and_increment(TEST_ORG_ID, UsageCategory.TRACE_EVALS, count=100)
    assert n == 1_000_099


async def test_hobby_bulk_fitting_exactly_at_limit_succeeds(db_session, redis_client):
    """A bulk increment that lands exactly on the limit should succeed."""
    repo = BillingRepository(db_session)
    sub = await repo.create_subscription(TEST_ORG_ID)
    await db_session.commit()
    key = f"pp:usage:{TEST_ORG_ID}:{sub.current_period_start.strftime('%Y-%m-%d')}"
    await redis_client.hset(key, "trace_evals", "95")
    svc = UsageService(redis_client, db_session)
    n = await svc.check_and_increment(TEST_ORG_ID, UsageCategory.TRACE_EVALS, count=5)
    assert n == 100


async def test_no_subscription_raises_quota_error(db_session, redis_client):
    """A request from an org with no subscription should be rejected."""
    svc = UsageService(redis_client, db_session)
    with pytest.raises(QuotaExceededError, match="No active subscription"):
        await svc.check_and_increment(TEST_ORG_ID, UsageCategory.TRACES)


async def test_canceled_subscription_raises_quota_error(db_session, redis_client):
    """A CANCELED subscription should block all usage."""
    repo = BillingRepository(db_session)
    await repo.create_subscription(TEST_ORG_ID)
    await repo.update_subscription(TEST_ORG_ID, status=SubscriptionStatus.CANCELED.value)
    await db_session.commit()
    svc = UsageService(redis_client, db_session)
    with pytest.raises(QuotaExceededError, match="not active"):
        await svc.check_and_increment(TEST_ORG_ID, UsageCategory.TRACES)


# ---------------------------------------------------------------------------
# Overage billing: delta calculation & idempotency
# ---------------------------------------------------------------------------


async def test_unreported_overages_computes_correct_delta(db_session, redis_client):
    """With watermark at 5000 and current at 5100 (base=5000), delta should be 100."""
    repo = BillingRepository(db_session)
    sub = await repo.create_subscription(
        TEST_ORG_ID,
        plan=SubscriptionPlan.PRO,
        stripe_subscription_id="sub_delta",
    )
    await repo.upsert_usage_counters(
        TEST_ORG_ID,
        sub.current_period_start,
        sub.current_period_end,
        trace_count=5100,
        trace_eval_count=5000,
        session_eval_count=50,
    )
    await db_session.commit()

    billing_svc = BillingService(db_session, redis_client=redis_client)
    overages = await billing_svc.calculate_unreported_overages(TEST_ORG_ID)

    assert overages.trace_overage == 100
    assert overages.trace_eval_overage == 0
    assert overages.session_eval_overage == 0
    assert overages.total_cost == OVERAGE_UNIT_PRICE * 100


async def test_unreported_overages_second_call_yields_only_new_delta(db_session, redis_client):
    """After watermark advances, the next delta only covers new usage."""
    repo = BillingRepository(db_session)
    sub = await repo.create_subscription(
        TEST_ORG_ID,
        plan=SubscriptionPlan.PRO,
        stripe_subscription_id="sub_delta2",
    )
    await repo.upsert_usage_counters(
        TEST_ORG_ID,
        sub.current_period_start,
        sub.current_period_end,
        trace_count=5100,
        trace_eval_count=5000,
        session_eval_count=50,
    )
    await repo.update_reported_usage(
        TEST_ORG_ID,
        sub.current_period_start,
        reported_trace_count=5100,
        reported_trace_eval_count=5000,
        reported_session_eval_count=50,
    )
    await db_session.commit()

    billing_svc = BillingService(db_session, redis_client=redis_client)
    overages = await billing_svc.calculate_unreported_overages(TEST_ORG_ID)
    assert overages.total_cost == Decimal("0")
    assert overages.trace_overage == 0


async def test_unreported_overages_incremental_growth(db_session, redis_client):
    """Watermark at 5100, usage grows to 5150 — delta should be 50."""
    repo = BillingRepository(db_session)
    sub = await repo.create_subscription(
        TEST_ORG_ID,
        plan=SubscriptionPlan.PRO,
        stripe_subscription_id="sub_inc",
    )
    await repo.upsert_usage_counters(
        TEST_ORG_ID,
        sub.current_period_start,
        sub.current_period_end,
        trace_count=5150,
        trace_eval_count=5000,
        session_eval_count=50,
    )
    await repo.update_reported_usage(
        TEST_ORG_ID,
        sub.current_period_start,
        reported_trace_count=5100,
        reported_trace_eval_count=5000,
        reported_session_eval_count=50,
    )
    await db_session.commit()

    billing_svc = BillingService(db_session, redis_client=redis_client)
    overages = await billing_svc.calculate_unreported_overages(TEST_ORG_ID)
    assert overages.trace_overage == 50
    assert overages.total_cost == OVERAGE_UNIT_PRICE * 50


async def test_unreported_overages_below_base_returns_zero(db_session, redis_client):
    """Usage below the base limit produces zero overage regardless of watermark."""
    repo = BillingRepository(db_session)
    sub = await repo.create_subscription(
        TEST_ORG_ID,
        plan=SubscriptionPlan.PRO,
        stripe_subscription_id="sub_below",
    )
    await repo.upsert_usage_counters(
        TEST_ORG_ID,
        sub.current_period_start,
        sub.current_period_end,
        trace_count=4000,
        trace_eval_count=3000,
        session_eval_count=50,
    )
    await db_session.commit()

    billing_svc = BillingService(db_session, redis_client=redis_client)
    overages = await billing_svc.calculate_unreported_overages(TEST_ORG_ID)
    assert overages.total_cost == Decimal("0")
    assert overages.trace_overage == 0
    assert overages.trace_eval_overage == 0


async def test_unreported_overages_cross_base_transition(db_session, redis_client):
    """Watermark below base (4800), current above base (5100) — delta = 100."""
    repo = BillingRepository(db_session)
    sub = await repo.create_subscription(
        TEST_ORG_ID,
        plan=SubscriptionPlan.PRO,
        stripe_subscription_id="sub_cross",
    )
    await repo.upsert_usage_counters(
        TEST_ORG_ID,
        sub.current_period_start,
        sub.current_period_end,
        trace_count=5100,
        trace_eval_count=4000,
        session_eval_count=50,
    )
    await repo.update_reported_usage(
        TEST_ORG_ID,
        sub.current_period_start,
        reported_trace_count=4800,
        reported_trace_eval_count=4000,
        reported_session_eval_count=50,
    )
    await db_session.commit()

    billing_svc = BillingService(db_session, redis_client=redis_client)
    overages = await billing_svc.calculate_unreported_overages(TEST_ORG_ID)
    assert overages.trace_overage == 100


async def test_unreported_overages_billed_period_returns_zero(db_session, redis_client):
    """A billed usage record should produce zero overages."""
    repo = BillingRepository(db_session)
    sub = await repo.create_subscription(
        TEST_ORG_ID,
        plan=SubscriptionPlan.PRO,
        stripe_subscription_id="sub_billed",
    )
    await repo.upsert_usage_counters(
        TEST_ORG_ID,
        sub.current_period_start,
        sub.current_period_end,
        trace_count=10000,
        trace_eval_count=10000,
        session_eval_count=500,
    )
    await repo.mark_billed(TEST_ORG_ID, sub.current_period_start, "inv_xxx")
    await db_session.commit()

    billing_svc = BillingService(db_session, redis_client=redis_client)
    overages = await billing_svc.calculate_unreported_overages(TEST_ORG_ID)
    assert overages.total_cost == Decimal("0")


async def test_unreported_overages_hobby_returns_zero(db_session, redis_client):
    """HOBBY plans (non pay-as-you-go) should never produce overages."""
    repo = BillingRepository(db_session)
    sub = await repo.create_subscription(TEST_ORG_ID)
    await repo.upsert_usage_counters(
        TEST_ORG_ID,
        sub.current_period_start,
        sub.current_period_end,
        trace_count=200,
        trace_eval_count=200,
        session_eval_count=20,
    )
    await db_session.commit()

    billing_svc = BillingService(db_session, redis_client=redis_client)
    overages = await billing_svc.calculate_unreported_overages(TEST_ORG_ID)
    assert overages.total_cost == Decimal("0")


async def test_report_overages_advances_watermark(db_session, redis_client):
    """After reporting, the watermark should match the current usage snapshot."""
    repo = BillingRepository(db_session)
    sub = await repo.create_subscription(
        TEST_ORG_ID,
        plan=SubscriptionPlan.PRO,
        stripe_customer_id="cus_test",
        stripe_subscription_id="sub_wm",
    )
    await repo.upsert_usage_counters(
        TEST_ORG_ID,
        sub.current_period_start,
        sub.current_period_end,
        trace_count=5200,
        trace_eval_count=5000,
        session_eval_count=50,
    )
    await db_session.commit()

    billing_svc = BillingService(db_session, redis_client=redis_client)

    with patch("stripe.InvoiceItem.create"):
        result = await billing_svc.report_overages_to_stripe(TEST_ORG_ID)
    await db_session.commit()

    assert result is True

    usage = await repo.get_current_usage_record(TEST_ORG_ID, sub.current_period_start)
    assert usage is not None
    assert usage.reported_trace_count == 5200
    assert usage.reported_trace_eval_count == 5000
    assert usage.reported_session_eval_count == 50


async def test_report_overages_idempotent_on_second_call(db_session, redis_client):
    """Second call after watermark advance should be a no-op."""
    repo = BillingRepository(db_session)
    sub = await repo.create_subscription(
        TEST_ORG_ID,
        plan=SubscriptionPlan.PRO,
        stripe_customer_id="cus_test2",
        stripe_subscription_id="sub_idem",
    )
    await repo.upsert_usage_counters(
        TEST_ORG_ID,
        sub.current_period_start,
        sub.current_period_end,
        trace_count=5200,
        trace_eval_count=5000,
        session_eval_count=50,
    )
    await db_session.commit()

    billing_svc = BillingService(db_session, redis_client=redis_client)

    with patch("stripe.InvoiceItem.create") as mock_create:
        await billing_svc.report_overages_to_stripe(TEST_ORG_ID)
        await db_session.commit()

        result = await billing_svc.report_overages_to_stripe(TEST_ORG_ID)
        await db_session.commit()

    assert result is False
    assert mock_create.call_count == 1


async def test_overage_lock_prevents_concurrent_reporting(db_session, redis_client):
    """When the lock is held, a second attempt should be skipped."""
    billing_svc = BillingService(db_session, redis_client=redis_client)

    assert await billing_svc.acquire_overage_lock(TEST_ORG_ID) is True
    assert await billing_svc.acquire_overage_lock(TEST_ORG_ID) is False

    await billing_svc.release_overage_lock(TEST_ORG_ID)
    assert await billing_svc.acquire_overage_lock(TEST_ORG_ID) is True
    await billing_svc.release_overage_lock(TEST_ORG_ID)
