"""Plan definitions and pricing configuration.

Single source of truth for what each subscription tier includes.
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.core.billing.entities import PlanConfig
from app.registry.constants import SubscriptionPlan

PLAN_LIMITS: dict[SubscriptionPlan, PlanConfig] = {
    SubscriptionPlan.HOBBY: PlanConfig(
        included_events=1_000,
        monitoring_allowed=False,
        max_members=1,
        pay_as_you_go=False,
        monthly_price_cents=0,
    ),
    SubscriptionPlan.STARTUP: PlanConfig(
        included_events=100_000,
        monitoring_allowed=True,
        max_members=10,
        pay_as_you_go=True,
        monthly_price_cents=29_900,
    ),
    SubscriptionPlan.ENTERPRISE: PlanConfig(
        included_events=0,
        monitoring_allowed=True,
        max_members=None,
        pay_as_you_go=True,
        monthly_price_cents=0,
    ),
    SubscriptionPlan.DEVELOPMENT: PlanConfig(
        included_events=None,
        monitoring_allowed=True,
        max_members=1,
        pay_as_you_go=False,
        monthly_price_cents=0,
    ),
}

OVERAGE_UNIT_PRICE = Decimal("0.004")

MAX_OWNED_ORGS = 2


def get_plan_config(plan: SubscriptionPlan) -> PlanConfig:
    """Return the static configuration for a plan tier."""
    return PLAN_LIMITS[plan]


def plan_pricing(plan: SubscriptionPlan) -> dict[str, Any]:
    """Build the first price snapshot. Subsequent reports reuse the saved snapshot."""
    rate = str(OVERAGE_UNIT_PRICE)
    if plan == SubscriptionPlan.ENTERPRISE:
        return {"unit_price": rate, "traces": 0, "trace_evals": 0, "session_evals": 0}
    return {"unit_price": rate, "included_events": get_plan_config(plan).included_events}


def overage_by_item(counts: dict[str, int], pricing: dict[str, Any]) -> dict[str, int]:
    """Apply the allowance once per billable item in the period's price snapshot."""
    if "included_events" in pricing:
        included = pricing["included_events"]
        return {"events": 0 if included is None else max(0, sum(counts.values()) - included)}
    return {category: max(0, count - pricing[category]) for category, count in counts.items()}


def usd_cents(amount: Decimal) -> int:
    """Round a USD amount at the invoice currency boundary."""
    return int((amount * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
