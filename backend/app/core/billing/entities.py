"""Pure domain entities for the Billing bounded context.

These models carry no infrastructure dependencies.  They represent
subscriptions, usage records, and plan configuration.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, computed_field

from app.registry.constants import SubscriptionPlan, SubscriptionStatus

USAGE_COUNTERS = {"traces": "trace_count", "trace_evals": "trace_eval_count", "session_evals": "session_eval_count"}


class Subscription(BaseModel):
    """An organization's subscription to a PandaProbe plan."""

    id: UUID
    org_id: UUID
    plan: SubscriptionPlan
    status: SubscriptionStatus
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None
    current_period_start: datetime
    current_period_end: datetime
    canceled_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class UsageRecord(BaseModel):
    """Aggregated usage counters for a single billing period."""

    id: UUID
    org_id: UUID
    period_start: datetime
    period_end: datetime
    trace_count: int = 0
    trace_eval_count: int = 0
    session_eval_count: int = 0
    reported_trace_count: int = 0
    reported_trace_eval_count: int = 0
    reported_session_eval_count: int = 0
    billed: bool = False
    stripe_invoice_id: str | None = None
    created_at: datetime
    updated_at: datetime

    @property
    def counts(self) -> dict[str, int]:
        """Return absolute database counts keyed by usage category."""
        return {category: getattr(self, counter) for category, counter in USAGE_COUNTERS.items()}

    @property
    def reported_counts(self) -> dict[str, int]:
        """Return confirmed usage watermarks keyed by usage category."""
        return {category: getattr(self, f"reported_{counter}") for category, counter in USAGE_COUNTERS.items()}


class PlanConfig(BaseModel):
    """Static configuration for a subscription plan tier."""

    included_events: int | None = Field(ge=0, description="Shared event allowance per period, or unlimited")
    monitoring_allowed: bool = Field(description="Whether monitor creation is permitted")
    max_members: int | None = Field(description="Max org members; None = unlimited")
    pay_as_you_go: bool = Field(description="Whether overages are billed rather than blocked")
    monthly_price_cents: int = Field(description="Base monthly price in USD cents")


class BillingReport(BaseModel):
    """An immutable usage snapshot plus recoverable Stripe delivery state."""

    id: UUID
    usage_record_id: UUID
    stripe_customer_id: str
    stripe_subscription_id: str | None
    closing_invoice_id: str | None
    snapshot_trace_count: int
    snapshot_trace_eval_count: int
    snapshot_session_eval_count: int
    pricing: dict[str, Any]
    requests: dict[str, Any]
    attempted_at: dict[str, str]
    stripe_item_ids: dict[str, str]
    status: str
    last_error: str | None
    created_at: datetime
    updated_at: datetime

    @property
    def snapshot_counts(self) -> dict[str, int]:
        """Return the three counters recorded together for this report."""
        return {category: getattr(self, f"snapshot_{counter}") for category, counter in USAGE_COUNTERS.items()}


class UsageSummary(BaseModel):
    """Current-period usage snapshot returned to the API caller."""

    plan: SubscriptionPlan
    status: SubscriptionStatus
    period_start: datetime
    period_end: datetime
    traces: int = 0
    trace_evals: int = 0
    session_evals: int = 0
    limits: PlanConfig

    @computed_field
    @property
    def total_events(self) -> int:
        """Count the three billable event types across the organization."""
        return self.traces + self.trace_evals + self.session_evals

    @computed_field
    @property
    def remaining_events(self) -> int | None:
        """Return unused included events, or None for unlimited usage."""
        included = self.limits.included_events
        return None if included is None else max(0, included - self.total_events)


class CategoryUsage(BaseModel):
    """Raw usage in a single category."""

    used: int


class BillingResponse(BaseModel):
    """Current-period billing overview with cost projections."""

    plan: SubscriptionPlan
    period_start: str
    period_end: str
    base_price_cents: int
    pay_as_you_go: bool
    overage_unit_price: str
    traces: CategoryUsage
    trace_evals: CategoryUsage
    session_evals: CategoryUsage
    total_events: int
    included_events: int | None
    remaining_events: int | None
    overage_events: int
    total_overage_cost: str
    reported_overage_cost: str
    pending_overage_cost: str
    estimated_total_cents: int


class OverageDetail(BaseModel):
    """Breakdown of overage charges for a billing period.

    The ``snapshot_*`` fields record the absolute counter values at the
    time of calculation so the caller can advance the high-water mark
    after successfully reporting the delta to Stripe.
    """

    overage_events: int = 0
    total_cost: Decimal = Decimal("0")
    snapshot_trace_count: int = 0
    snapshot_trace_eval_count: int = 0
    snapshot_session_eval_count: int = 0
