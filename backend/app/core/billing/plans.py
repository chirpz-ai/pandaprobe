"""Plan definitions and pricing configuration.

Single source of truth for what each subscription tier includes.
"""

from decimal import Decimal

from app.core.billing.entities import PlanConfig
from app.registry.constants import SubscriptionPlan, UsageCategory

PLAN_LIMITS: dict[SubscriptionPlan, PlanConfig] = {
    SubscriptionPlan.HOBBY: PlanConfig(
        base_traces=100,
        base_trace_evals=100,
        base_session_evals=10,
        monitoring_allowed=False,
        max_members=1,
        pay_as_you_go=False,
        monthly_price_cents=0,
    ),
    SubscriptionPlan.PRO: PlanConfig(
        base_traces=5_000,
        base_trace_evals=5_000,
        base_session_evals=100,
        monitoring_allowed=True,
        max_members=2,
        pay_as_you_go=True,
        monthly_price_cents=2_900,
    ),
    SubscriptionPlan.STARTUP: PlanConfig(
        base_traces=50_000,
        base_trace_evals=50_000,
        base_session_evals=1_000,
        monitoring_allowed=True,
        max_members=10,
        pay_as_you_go=True,
        monthly_price_cents=29_900,
    ),
    SubscriptionPlan.ENTERPRISE: PlanConfig(
        base_traces=0,
        base_trace_evals=0,
        base_session_evals=0,
        monitoring_allowed=True,
        max_members=None,
        pay_as_you_go=True,
        monthly_price_cents=0,
    ),
    SubscriptionPlan.DEVELOPMENT: PlanConfig(
        base_traces=None,
        base_trace_evals=None,
        base_session_evals=None,
        monitoring_allowed=True,
        max_members=None,
        pay_as_you_go=False,
        monthly_price_cents=0,
    ),
}

OVERAGE_UNIT_PRICE = Decimal("0.004")

MAX_OWNED_ORGS = 2


def get_plan_config(plan: SubscriptionPlan) -> PlanConfig:
    """Return the static configuration for a plan tier."""
    return PLAN_LIMITS[plan]


def get_limit_for_category(plan: SubscriptionPlan, category: UsageCategory) -> int | None:
    """Return the included-unit count for a usage category under the given plan.

    Returns ``0`` for ENTERPRISE (unlimited access, all usage billed as
    overage).  Returns ``None`` when no config exists.
    """
    cfg = PLAN_LIMITS[plan]
    match category:
        case UsageCategory.TRACES:
            return cfg.base_traces
        case UsageCategory.TRACE_EVALS:
            return cfg.base_trace_evals
        case UsageCategory.SESSION_EVALS:
            return cfg.base_session_evals
