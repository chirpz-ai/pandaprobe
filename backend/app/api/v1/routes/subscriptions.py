"""Routes for subscription management and usage information.

All endpoints require a valid Bearer JWT.
"""

from decimal import Decimal
from typing import Any
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.context import ApiContext
from app.api.dependencies import get_api_context
from app.core.billing.plans import OVERAGE_UNIT_PRICE, PLAN_LIMITS, get_plan_config
from app.infrastructure.db.engine import get_db_session
from app.infrastructure.db.repositories.billing_repo import BillingRepository
from app.infrastructure.redis.client import get_redis
from app.registry.constants import SubscriptionPlan, SubscriptionStatus
from app.registry.exceptions import AuthenticationError, NotFoundError, ValidationError
from app.services.billing_service import BillingService
from app.services.usage_service import UsageService

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


def _require_user(ctx: ApiContext) -> None:
    if ctx.user is None:
        raise AuthenticationError("This endpoint requires user authentication (Bearer token).")


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SubscriptionResponse(BaseModel):
    """Public representation of the org's subscription."""

    id: UUID
    org_id: UUID
    plan: SubscriptionPlan
    status: SubscriptionStatus
    current_period_start: str
    current_period_end: str
    canceled_at: str | None = None
    created_at: str


class UsageResponse(BaseModel):
    """Current-period usage snapshot."""

    plan: SubscriptionPlan
    status: SubscriptionStatus
    period_start: str
    period_end: str
    traces: int = 0
    trace_evals: int = 0
    session_evals: int = 0
    limits: dict[str, Any] = Field(default_factory=dict)


class CategoryBreakdown(BaseModel):
    """Overage cost breakdown for a single usage category."""

    used: int
    included: int | None
    overage_units: int
    overage_cost: str


class BillingResponse(BaseModel):
    """Current-period billing overview with cost projections."""

    plan: SubscriptionPlan
    period_start: str
    period_end: str
    base_price_cents: int
    overage_unit_price: str
    traces: CategoryBreakdown
    trace_evals: CategoryBreakdown
    session_evals: CategoryBreakdown
    total_overage_cost: str
    estimated_total_cents: int


class UsageHistoryItem(BaseModel):
    """One billing period's usage summary."""

    period_start: str
    period_end: str
    trace_count: int
    trace_eval_count: int
    session_eval_count: int
    billed: bool
    stripe_invoice_id: str | None = None


class PlanInfo(BaseModel):
    """Public representation of a plan tier."""

    name: str
    base_traces: int | None
    base_trace_evals: int | None
    base_session_evals: int | None
    monitoring_allowed: bool
    max_members: int | None
    pay_as_you_go: bool
    monthly_price_cents: int
    overage_unit_price: str


class CheckoutRequest(BaseModel):
    """Payload for creating a Stripe Checkout session."""

    plan: SubscriptionPlan
    success_url: str
    cancel_url: str


class CheckoutResponse(BaseModel):
    """Redirect URL for the Stripe Checkout session."""

    checkout_url: str


class PortalRequest(BaseModel):
    """Payload for creating a Stripe Customer Portal session."""

    return_url: str


class PortalResponse(BaseModel):
    """Redirect URL for the Stripe Customer Portal."""

    portal_url: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=SubscriptionResponse)
async def get_subscription(
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> SubscriptionResponse:
    """Get the current organization's subscription.

    Auth: `Bearer`
    """
    _require_user(ctx)

    repo = BillingRepository(session)
    sub = await repo.get_subscription_by_org(ctx.organization.id)
    if sub is None:
        raise NotFoundError("No subscription found for this organization.")

    return SubscriptionResponse(
        id=sub.id,
        org_id=sub.org_id,
        plan=sub.plan,
        status=sub.status,
        current_period_start=sub.current_period_start.isoformat(),
        current_period_end=sub.current_period_end.isoformat(),
        canceled_at=sub.canceled_at.isoformat() if sub.canceled_at else None,
        created_at=sub.created_at.isoformat(),
    )


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    ctx: ApiContext = Depends(get_api_context),
    redis_client: aioredis.Redis = Depends(get_redis),
    session: AsyncSession = Depends(get_db_session),
) -> UsageResponse:
    """Get the current period's usage breakdown.

    Auth: `Bearer`
    """
    _require_user(ctx)
    usage_svc = UsageService(redis_client, session)
    summary = await usage_svc.get_current_usage(ctx.organization.id)
    return UsageResponse(
        plan=summary.plan,
        status=summary.status,
        period_start=summary.period_start.isoformat(),
        period_end=summary.period_end.isoformat(),
        traces=summary.traces,
        trace_evals=summary.trace_evals,
        session_evals=summary.session_evals,
        limits=summary.limits,
    )


@router.get("/billing", response_model=BillingResponse)
async def get_billing(
    ctx: ApiContext = Depends(get_api_context),
    redis_client: aioredis.Redis = Depends(get_redis),
    session: AsyncSession = Depends(get_db_session),
) -> BillingResponse:
    """Get the current billing period's cost breakdown including overages.

    Returns the base plan price, per-category overage breakdown, and
    the estimated total for the current period.

    Auth: `Bearer`
    """
    _require_user(ctx)

    repo = BillingRepository(session)
    sub = await repo.get_subscription_by_org(ctx.organization.id)
    if sub is None:
        raise NotFoundError("No subscription found for this organization.")

    plan = SubscriptionPlan(sub.plan)
    plan_cfg = get_plan_config(plan)

    usage_svc = UsageService(redis_client, session)
    summary = await usage_svc.get_current_usage(ctx.organization.id)

    billing_svc = BillingService(session, redis_client=redis_client)
    overages = await billing_svc.calculate_unreported_overages(ctx.organization.id)

    base_t = plan_cfg.base_traces or 0
    base_e = plan_cfg.base_trace_evals or 0
    base_s = plan_cfg.base_session_evals or 0

    usage_record = await repo.get_current_usage_record(ctx.organization.id, sub.current_period_start)
    already_reported_cost = Decimal("0")
    if usage_record:
        prev_t = max(0, usage_record.reported_trace_count - base_t)
        prev_e = max(0, usage_record.reported_trace_eval_count - base_e)
        prev_s = max(0, usage_record.reported_session_eval_count - base_s)
        already_reported_cost = OVERAGE_UNIT_PRICE * (prev_t + prev_e + prev_s)

    total_t_over = max(0, summary.traces - base_t)
    total_e_over = max(0, summary.trace_evals - base_e)
    total_s_over = max(0, summary.session_evals - base_s)
    total_overage = OVERAGE_UNIT_PRICE * (total_t_over + total_e_over + total_s_over)

    estimated_total_cents = plan_cfg.monthly_price_cents + int(total_overage * 100)

    return BillingResponse(
        plan=plan,
        period_start=sub.current_period_start.isoformat(),
        period_end=sub.current_period_end.isoformat(),
        base_price_cents=plan_cfg.monthly_price_cents,
        overage_unit_price=str(OVERAGE_UNIT_PRICE),
        traces=CategoryBreakdown(
            used=summary.traces,
            included=plan_cfg.base_traces,
            overage_units=total_t_over,
            overage_cost=str(OVERAGE_UNIT_PRICE * total_t_over),
        ),
        trace_evals=CategoryBreakdown(
            used=summary.trace_evals,
            included=plan_cfg.base_trace_evals,
            overage_units=total_e_over,
            overage_cost=str(OVERAGE_UNIT_PRICE * total_e_over),
        ),
        session_evals=CategoryBreakdown(
            used=summary.session_evals,
            included=plan_cfg.base_session_evals,
            overage_units=total_s_over,
            overage_cost=str(OVERAGE_UNIT_PRICE * total_s_over),
        ),
        total_overage_cost=str(total_overage),
        estimated_total_cents=estimated_total_cents,
    )


@router.get("/invoices", response_model=list[UsageHistoryItem])
async def get_invoices(
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=12, ge=1, le=36),
) -> list[UsageHistoryItem]:
    """List past billing period usage records.

    Returns up to ``limit`` periods, most recent first.

    Auth: `Bearer`
    """
    _require_user(ctx)

    repo = BillingRepository(session)
    records = await repo.list_usage_history(ctx.organization.id, limit=limit)

    return [
        UsageHistoryItem(
            period_start=r.period_start.isoformat(),
            period_end=r.period_end.isoformat(),
            trace_count=r.trace_count,
            trace_eval_count=r.trace_eval_count,
            session_eval_count=r.session_eval_count,
            billed=r.billed,
            stripe_invoice_id=r.stripe_invoice_id,
        )
        for r in records
    ]


@router.get("/plans", response_model=list[PlanInfo])
async def get_plans() -> list[PlanInfo]:
    """Return all available plans with their limits and pricing.

    No auth required — public data for plan comparison UI.
    """
    return [
        PlanInfo(
            name=plan.value,
            base_traces=cfg.base_traces,
            base_trace_evals=cfg.base_trace_evals,
            base_session_evals=cfg.base_session_evals,
            monitoring_allowed=cfg.monitoring_allowed,
            max_members=cfg.max_members,
            pay_as_you_go=cfg.pay_as_you_go,
            monthly_price_cents=cfg.monthly_price_cents,
            overage_unit_price=str(OVERAGE_UNIT_PRICE),
        )
        for plan, cfg in PLAN_LIMITS.items()
    ]


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    body: CheckoutRequest,
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> CheckoutResponse:
    """Create a Stripe Checkout session for upgrading the subscription.

    Auth: `Bearer` - role: `OWNER` or `ADMIN`
    """
    _require_user(ctx)
    if body.plan not in (SubscriptionPlan.PRO, SubscriptionPlan.STARTUP):
        raise ValidationError("Checkout is only available for PRO and STARTUP plans.")

    billing_svc = BillingService(session)
    url = await billing_svc.create_checkout_session(
        org_id=ctx.organization.id,
        plan=body.plan,
        success_url=body.success_url,
        cancel_url=body.cancel_url,
    )
    return CheckoutResponse(checkout_url=url)


@router.post("/portal", response_model=PortalResponse)
async def create_portal(
    body: PortalRequest,
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> PortalResponse:
    """Create a Stripe Customer Portal session for self-service billing management.

    Auth: `Bearer` - role: `OWNER` or `ADMIN`
    """
    _require_user(ctx)
    billing_svc = BillingService(session)
    url = await billing_svc.create_portal_session(
        org_id=ctx.organization.id,
        return_url=body.return_url,
    )
    return PortalResponse(portal_url=url)
