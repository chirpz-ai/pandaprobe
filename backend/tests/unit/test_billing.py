"""Unit tests for billing, usage, and subscription domain logic (no database required)."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.billing.entities import PlanConfig, Subscription, UsageRecord, UsageSummary
from app.core.billing.plans import (
    OVERAGE_UNIT_PRICE,
    PLAN_LIMITS,
    get_plan_config,
    overage_by_item,
)
from app.registry.constants import SubscriptionPlan, SubscriptionStatus, UsageCategory
from app.registry.exceptions import QuotaExceededError


def test_get_plan_config_returns_hobby_config() -> None:
    cfg = get_plan_config(SubscriptionPlan.HOBBY)
    assert cfg.included_events == 1_000
    assert cfg.monitoring_allowed is False
    assert cfg.max_members == 1
    assert cfg.pay_as_you_go is False
    assert cfg.monthly_price_cents == 0


def test_get_plan_config_returns_startup_config() -> None:
    cfg = get_plan_config(SubscriptionPlan.STARTUP)
    assert cfg.included_events == 100_000
    assert cfg.monitoring_allowed is True
    assert cfg.max_members == 10
    assert cfg.pay_as_you_go is True
    assert cfg.monthly_price_cents == 29_900


def test_get_plan_config_returns_enterprise_config() -> None:
    cfg = get_plan_config(SubscriptionPlan.ENTERPRISE)
    assert cfg.included_events == 0
    assert cfg.monitoring_allowed is True
    assert cfg.max_members is None
    assert cfg.pay_as_you_go is True
    assert cfg.monthly_price_cents == 0


def test_development_is_unlimited_and_unbilled() -> None:
    cfg = get_plan_config(SubscriptionPlan.DEVELOPMENT)
    assert cfg.included_events is None
    assert not cfg.pay_as_you_go


def test_plan_limits_has_four_entries() -> None:
    assert len(PLAN_LIMITS) == 4
    assert set(PLAN_LIMITS.keys()) == {
        SubscriptionPlan.HOBBY,
        SubscriptionPlan.STARTUP,
        SubscriptionPlan.ENTERPRISE,
        SubscriptionPlan.DEVELOPMENT,
    }


def test_overage_unit_price() -> None:
    assert OVERAGE_UNIT_PRICE == Decimal("0.004")


def test_plan_config_accepts_valid_fields() -> None:
    cfg = PlanConfig(
        included_events=3,
        monitoring_allowed=True,
        max_members=5,
        pay_as_you_go=True,
        monthly_price_cents=100,
    )
    assert cfg.included_events == 3


def test_plan_config_rejects_invalid_field_types() -> None:
    with pytest.raises(ValidationError):
        PlanConfig(
            included_events="not_int",
            monitoring_allowed=False,
            max_members=1,
            pay_as_you_go=False,
            monthly_price_cents=0,
        )


def test_subscription_model_all_fields() -> None:
    sid = uuid4()
    oid = uuid4()
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    end = datetime(2025, 2, 1, tzinfo=timezone.utc)
    created = datetime(2024, 12, 1, tzinfo=timezone.utc)
    updated = datetime(2024, 12, 15, tzinfo=timezone.utc)
    canceled = datetime(2025, 3, 1, tzinfo=timezone.utc)
    sub = Subscription(
        id=sid,
        org_id=oid,
        plan=SubscriptionPlan.STARTUP,
        status=SubscriptionStatus.ACTIVE,
        stripe_customer_id="cus_123",
        stripe_subscription_id="sub_456",
        current_period_start=start,
        current_period_end=end,
        canceled_at=canceled,
        created_at=created,
        updated_at=updated,
    )
    assert sub.id == sid
    assert sub.org_id == oid
    assert sub.plan == SubscriptionPlan.STARTUP
    assert sub.status == SubscriptionStatus.ACTIVE
    assert sub.stripe_customer_id == "cus_123"
    assert sub.stripe_subscription_id == "sub_456"
    assert sub.current_period_start == start
    assert sub.current_period_end == end
    assert sub.canceled_at == canceled
    assert sub.created_at == created
    assert sub.updated_at == updated


def test_usage_record_defaults() -> None:
    rid = uuid4()
    oid = uuid4()
    ps = datetime(2025, 1, 1, tzinfo=timezone.utc)
    pe = datetime(2025, 2, 1, tzinfo=timezone.utc)
    ts = datetime(2025, 1, 5, tzinfo=timezone.utc)
    rec = UsageRecord(
        id=rid,
        org_id=oid,
        period_start=ps,
        period_end=pe,
        created_at=ts,
        updated_at=ts,
    )
    assert rec.trace_count == 0
    assert rec.trace_eval_count == 0
    assert rec.session_eval_count == 0
    assert rec.billed is False
    assert rec.stripe_invoice_id is None


def test_usage_summary_defaults() -> None:
    ps = datetime(2025, 1, 1, tzinfo=timezone.utc)
    pe = datetime(2025, 2, 1, tzinfo=timezone.utc)
    summary = UsageSummary(
        plan=SubscriptionPlan.HOBBY,
        status=SubscriptionStatus.ACTIVE,
        period_start=ps,
        period_end=pe,
        limits=get_plan_config(SubscriptionPlan.HOBBY),
    )
    assert summary.traces == 0
    assert summary.trace_evals == 0
    assert summary.session_evals == 0
    assert summary.total_events == 0
    assert summary.remaining_events == 1_000


@pytest.mark.parametrize(
    ("counts", "expected"),
    [((100_000, 0, 0), 0), ((70_000, 20_000, 10_000), 0), ((0, 0, 100_000), 0), ((70_000, 25_000, 10_000), 5_000)],
)
def test_startup_applies_one_allowance(counts, expected) -> None:
    pricing = {"included_events": get_plan_config(SubscriptionPlan.STARTUP).included_events}
    assert overage_by_item(dict(zip(("traces", "trace_evals", "session_evals"), counts, strict=True)), pricing) == {
        "events": expected
    }


def test_subscription_plan_enum_members() -> None:
    assert list(SubscriptionPlan) == [
        SubscriptionPlan.HOBBY,
        SubscriptionPlan.STARTUP,
        SubscriptionPlan.ENTERPRISE,
        SubscriptionPlan.DEVELOPMENT,
    ]


def test_subscription_status_enum_members() -> None:
    assert list(SubscriptionStatus) == [
        SubscriptionStatus.ACTIVE,
        SubscriptionStatus.PAST_DUE,
        SubscriptionStatus.CANCELED,
        SubscriptionStatus.INCOMPLETE,
    ]


def test_usage_category_enum_members() -> None:
    assert list(UsageCategory) == [
        UsageCategory.TRACES,
        UsageCategory.TRACE_EVALS,
        UsageCategory.SESSION_EVALS,
    ]


def test_quota_exceeded_error_status_code() -> None:
    err = QuotaExceededError()
    assert err.status_code == 429


def test_quota_exceeded_error_default_detail() -> None:
    err = QuotaExceededError()
    assert err.detail == "Usage quota exceeded for your current plan."


def test_quota_exceeded_error_custom_detail() -> None:
    err = QuotaExceededError("Custom quota message.")
    assert err.detail == "Custom quota message."
