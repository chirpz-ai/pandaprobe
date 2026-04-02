"""Pure domain entities for the Billing bounded context.

These models carry no infrastructure dependencies.  They represent
subscriptions, usage records, and plan configuration.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.registry.constants import SubscriptionPlan, SubscriptionStatus


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
    billed: bool = False
    stripe_invoice_id: str | None = None
    created_at: datetime
    updated_at: datetime


class PlanConfig(BaseModel):
    """Static configuration for a subscription plan tier."""

    base_traces: int | None = Field(description="Included traces per period; None = unlimited")
    base_trace_evals: int | None = Field(description="Included trace evaluations per period")
    base_session_evals: int | None = Field(description="Included session evaluations per period")
    monitoring_allowed: bool = Field(description="Whether monitor creation is permitted")
    max_members: int | None = Field(description="Max org members; None = unlimited")
    pay_as_you_go: bool = Field(description="Whether overages are billed rather than blocked")
    monthly_price_cents: int = Field(description="Base monthly price in USD cents")


class UsageSummary(BaseModel):
    """Current-period usage snapshot returned to the API caller."""

    plan: SubscriptionPlan
    status: SubscriptionStatus
    period_start: datetime
    period_end: datetime
    traces: int = 0
    trace_evals: int = 0
    session_evals: int = 0
    limits: dict[str, Any] = Field(default_factory=dict)


class OverageDetail(BaseModel):
    """Breakdown of overage charges for a billing period."""

    trace_overage: int = 0
    trace_eval_overage: int = 0
    session_eval_overage: int = 0
    trace_overage_cost: Decimal = Decimal("0")
    trace_eval_overage_cost: Decimal = Decimal("0")
    session_eval_overage_cost: Decimal = Decimal("0")
    total_cost: Decimal = Decimal("0")
