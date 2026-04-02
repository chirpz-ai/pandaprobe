import json

import pytest
import redis.asyncio as aioredis
from httpx import AsyncClient
from sqlalchemy import delete

from app.infrastructure.db.models import SubscriptionModel, UsageRecordModel
from app.infrastructure.db.repositories.billing_repo import BillingRepository
from app.registry.constants import SubscriptionPlan, UsageCategory
from app.registry.exceptions import QuotaExceededError
from app.registry.settings import settings
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
