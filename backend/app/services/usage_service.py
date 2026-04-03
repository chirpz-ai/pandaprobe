"""Real-time usage tracking via Redis with PostgreSQL durability.

The hot path (trace ingestion, eval creation) uses atomic Redis
operations for quota enforcement.  A periodic Celery task syncs the
Redis counters into the ``usage_records`` table for billing.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.billing.entities import Subscription, UsageSummary
from app.core.billing.plans import get_limit_for_category, get_plan_config
from app.infrastructure.db.repositories.billing_repo import BillingRepository
from app.logging import logger
from app.registry.constants import SubscriptionPlan, SubscriptionStatus, UsageCategory
from app.registry.exceptions import QuotaExceededError

_SUB_CACHE_PREFIX = "pp:sub:"
_USAGE_PREFIX = "pp:usage:"
_SUB_CACHE_TTL = 300  # 5 minutes
_USAGE_KEY_BUFFER_DAYS = 7

# Lua script: atomic check-and-increment with optional hard limit.
#   KEYS[1] = usage hash key
#   ARGV[1] = field name (e.g. "traces")
#   ARGV[2] = increment amount
#   ARGV[3] = hard limit (-1 = unlimited / no check)
#   ARGV[4] = TTL in seconds for the hash key
# Returns the new counter value, or -1 if the limit would be exceeded.
_CHECK_AND_INCREMENT_LUA = """
local current = redis.call('HINCRBY', KEYS[1], ARGV[1], tonumber(ARGV[2]))
local limit = tonumber(ARGV[3])
if limit >= 0 and current > limit then
    redis.call('HINCRBY', KEYS[1], ARGV[1], -tonumber(ARGV[2]))
    return -1
end
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[4]))
return current
"""


class UsageService:
    """Tracks billable actions with Redis atomicity and DB persistence."""

    def __init__(self, redis: aioredis.Redis, session: AsyncSession) -> None:
        self._redis = redis
        self._session = session
        self._billing_repo = BillingRepository(session)

    # -- Public API -----------------------------------------------------------

    async def check_and_increment(
        self,
        org_id: UUID,
        category: UsageCategory | str,
        count: int = 1,
    ) -> int:
        """Atomically increment usage and enforce quota.

        For HOBBY plans, raises ``QuotaExceededError`` when the hard
        limit is reached.  For paid plans, always succeeds (pay-as-you-go).

        Returns the new counter value after increment.
        """
        category = UsageCategory(category)
        sub = await self._get_subscription_cached(org_id)

        if sub is None:
            raise QuotaExceededError("No active subscription found for this organization.")

        if sub.status not in (SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE):
            raise QuotaExceededError("Your subscription is not active.")

        limit = get_limit_for_category(SubscriptionPlan(sub.plan), category)

        if limit is not None and limit == -1:
            raise QuotaExceededError(f"Your {sub.plan} plan does not include {category.value}. Please upgrade.")

        hard_limit: int
        if not get_plan_config(SubscriptionPlan(sub.plan)).pay_as_you_go:
            hard_limit = limit if limit is not None else -1
        else:
            hard_limit = -1

        usage_key = self._usage_key(org_id, sub.current_period_start)
        ttl = self._compute_ttl(sub.current_period_end)

        new_val = await self._redis.eval(  # type: ignore[union-attr]
            _CHECK_AND_INCREMENT_LUA,
            1,
            usage_key,
            category.value,
            str(count),
            str(hard_limit),
            str(ttl),
        )

        if new_val == -1:
            raise QuotaExceededError(
                f"You've reached the {category.value} limit ({limit}) for your {sub.plan} plan. "
                "Please upgrade to continue."
            )

        return int(new_val)

    async def get_current_usage(self, org_id: UUID) -> UsageSummary:
        """Return a snapshot of the current period's usage."""
        sub = await self._get_subscription_cached(org_id)
        if sub is None:
            return UsageSummary(
                plan=SubscriptionPlan.HOBBY,
                status=SubscriptionStatus.ACTIVE,
                period_start=datetime.now(timezone.utc),
                period_end=datetime.now(timezone.utc),
            )

        plan_cfg = get_plan_config(SubscriptionPlan(sub.plan))
        usage_key = self._usage_key(org_id, sub.current_period_start)
        raw = await self._redis.hgetall(usage_key)  # type: ignore[union-attr]

        return UsageSummary(
            plan=SubscriptionPlan(sub.plan),
            status=SubscriptionStatus(sub.status),
            period_start=sub.current_period_start,
            period_end=sub.current_period_end,
            traces=int(raw.get("traces", 0)),
            trace_evals=int(raw.get("trace_evals", 0)),
            session_evals=int(raw.get("session_evals", 0)),
            limits={
                "base_traces": plan_cfg.base_traces,
                "base_trace_evals": plan_cfg.base_trace_evals,
                "base_session_evals": plan_cfg.base_session_evals,
                "monitoring_allowed": plan_cfg.monitoring_allowed,
                "max_members": plan_cfg.max_members,
                "pay_as_you_go": plan_cfg.pay_as_you_go,
            },
        )

    async def require_monitoring_allowed(self, org_id: UUID) -> None:
        """Raise ``QuotaExceededError`` if the org's plan doesn't permit monitors."""
        sub = await self._get_subscription_cached(org_id)
        if sub is None:
            raise QuotaExceededError("No active subscription found for this organization.")
        plan_cfg = get_plan_config(SubscriptionPlan(sub.plan))
        if not plan_cfg.monitoring_allowed:
            raise QuotaExceededError(f"Monitoring is not available on your {sub.plan} plan. Please upgrade.")

    async def sync_to_database(self, org_id: UUID) -> None:
        """Persist Redis counters into the ``usage_records`` table."""
        sub = await self._billing_repo.get_subscription_by_org(org_id)
        if sub is None:
            return

        usage_key = self._usage_key(org_id, sub.current_period_start)
        raw = await self._redis.hgetall(usage_key)  # type: ignore[union-attr]
        if not raw:
            return

        await self._billing_repo.upsert_usage_counters(
            org_id=org_id,
            period_start=sub.current_period_start,
            period_end=sub.current_period_end,
            trace_count=int(raw.get("traces", 0)),
            trace_eval_count=int(raw.get("trace_evals", 0)),
            session_eval_count=int(raw.get("session_evals", 0)),
        )

    async def invalidate_subscription_cache(self, org_id: UUID) -> None:
        """Remove the cached subscription so the next lookup fetches from DB."""
        cache_key = f"{_SUB_CACHE_PREFIX}{org_id}"
        await self._redis.delete(cache_key)  # type: ignore[union-attr]

    async def delete_usage_key(self, org_id: UUID, period_start: datetime) -> None:
        """Remove the Redis usage hash for a given period."""
        usage_key = self._usage_key(org_id, period_start)
        await self._redis.delete(usage_key)  # type: ignore[union-attr]

    # -- Internal helpers -----------------------------------------------------

    async def _get_subscription_cached(self, org_id: UUID) -> Subscription | None:
        """Fetch the subscription, using Redis as a 5-minute read-through cache."""
        cache_key = f"{_SUB_CACHE_PREFIX}{org_id}"
        cached = await self._redis.get(cache_key)  # type: ignore[union-attr]

        if cached is not None:
            data = json.loads(cached)
            return Subscription(**data)

        sub = await self._billing_repo.get_subscription_by_org(org_id)
        if sub is None:
            return None

        payload = sub.model_dump(mode="json")
        await self._redis.set(cache_key, json.dumps(payload), ex=_SUB_CACHE_TTL)  # type: ignore[union-attr]
        return sub

    @staticmethod
    def _usage_key(org_id: UUID, period_start: datetime) -> str:
        date_str = period_start.strftime("%Y-%m-%d")
        return f"{_USAGE_PREFIX}{org_id}:{date_str}"

    @staticmethod
    def _compute_ttl(period_end: datetime) -> int:
        """TTL for the usage hash: period duration + buffer."""
        remaining = (period_end - datetime.now(timezone.utc)).total_seconds()
        buffer = _USAGE_KEY_BUFFER_DAYS * 86400
        return max(int(remaining) + buffer, buffer)
