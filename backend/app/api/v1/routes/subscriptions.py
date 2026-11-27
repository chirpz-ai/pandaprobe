"""Routes for subscription management and usage information.

Org-scoped endpoints live under ``/organizations/{org_id}/subscriptions``
and require explicit membership verification.  The static ``GET /plans``
endpoint remains at ``/subscriptions/plans`` (no org context needed).
"""

from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.context import ApiContext
from app.api.dependencies import get_api_context
from app.core.billing.entities import BillingResponse, UsageSummary
from app.core.billing.plans import PLAN_LIMITS, plan_pricing
from app.infrastructure.db.engine import get_db_session
from app.infrastructure.db.repositories.billing_repo import BillingRepository
from app.infrastructure.redis.client import get_redis
from app.registry.constants import SubscriptionPlan, SubscriptionStatus
from app.registry.exceptions import AuthenticationError, NotFoundError, ValidationError
from app.services.billing_service import BillingService, get_billing_overview
from app.services.identity_service import IdentityService
from app.services.usage_service import UsageService

router = APIRouter(prefix="/organizations/{org_id}/subscriptions", tags=["subscriptions"])
plans_router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


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


class UsageHistoryItem(BaseModel):
    """One billing period's usage summary."""

    period_start: str
    period_end: str
    total_events: int
    trace_count: int
    trace_eval_count: int
    session_eval_count: int
    billed: bool
    stripe_invoice_id: str | None = None


class PlanInfo(BaseModel):
    """Public representation of a plan tier."""

    name: str
    included_events: int | None
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
# Org-scoped endpoints — /organizations/{org_id}/subscriptions/...
# ---------------------------------------------------------------------------


@router.get("", response_model=SubscriptionResponse)
async def get_subscription(
    org_id: UUID,
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> SubscriptionResponse:
    """Get the organization's subscription.

    Auth: `Bearer` · role: any member
    """
    _require_user(ctx)
    svc = IdentityService(session)
    await svc.require_membership(ctx.user.id, org_id)

    repo = BillingRepository(session)
    sub = await repo.get_subscription_by_org(org_id)
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


@router.get("/usage", response_model=UsageSummary)
async def get_usage(
    org_id: UUID,
    ctx: ApiContext = Depends(get_api_context),
    redis_client: aioredis.Redis = Depends(get_redis),
    session: AsyncSession = Depends(get_db_session),
) -> UsageSummary:
    """Get the current period's usage breakdown.

    Auth: `Bearer` · role: any member
    """
    _require_user(ctx)
    svc = IdentityService(session)
    await svc.require_membership(ctx.user.id, org_id)

    usage_svc = UsageService(redis_client, session)
    return await usage_svc.get_current_usage(org_id)


@router.get("/billing", response_model=BillingResponse)
async def get_billing(
    org_id: UUID,
    ctx: ApiContext = Depends(get_api_context),
    redis_client: aioredis.Redis = Depends(get_redis),
    session: AsyncSession = Depends(get_db_session),
) -> BillingResponse:
    """Get the current billing period's cost breakdown including overages.

    Returns the base plan price, event overage, and
    the estimated total for the current period.

    Auth: `Bearer` · role: any member
    """
    _require_user(ctx)
    svc = IdentityService(session)
    await svc.require_membership(ctx.user.id, org_id)

    return await get_billing_overview(org_id, session, redis_client)


@router.get("/invoices", response_model=list[UsageHistoryItem])
async def get_invoices(
    org_id: UUID,
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
    limit: int = Query(default=12, ge=1, le=36),
) -> list[UsageHistoryItem]:
    """List past billing period usage records.

    Returns up to ``limit`` periods, most recent first.

    Auth: `Bearer` · role: any member
    """
    _require_user(ctx)
    svc = IdentityService(session)
    await svc.require_membership(ctx.user.id, org_id)

    repo = BillingRepository(session)
    records = await repo.list_usage_history(org_id, limit=limit)

    return [
        UsageHistoryItem(
            period_start=r.period_start.isoformat(),
            period_end=r.period_end.isoformat(),
            total_events=sum(r.counts.values()),
            trace_count=r.trace_count,
            trace_eval_count=r.trace_eval_count,
            session_eval_count=r.session_eval_count,
            billed=r.billed,
            stripe_invoice_id=r.stripe_invoice_id,
        )
        for r in records
    ]


@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    org_id: UUID,
    body: CheckoutRequest,
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> CheckoutResponse:
    """Create a Stripe Checkout session for upgrading the subscription.

    Auth: `Bearer` · role: `ADMIN` or `OWNER`
    """
    _require_user(ctx)
    await IdentityService(session).require_admin(ctx.user.id, org_id)
    if body.plan != SubscriptionPlan.STARTUP:
        raise ValidationError("Checkout is only available for STARTUP plans.")

    billing_svc = BillingService(session)
    url = await billing_svc.create_checkout_session(
        org_id=org_id,
        plan=body.plan,
        success_url=body.success_url,
        cancel_url=body.cancel_url,
    )
    return CheckoutResponse(checkout_url=url)


@router.post("/portal", response_model=PortalResponse)
async def create_portal(
    org_id: UUID,
    body: PortalRequest,
    ctx: ApiContext = Depends(get_api_context),
    session: AsyncSession = Depends(get_db_session),
) -> PortalResponse:
    """Create a Stripe Customer Portal session for self-service billing management.

    Auth: `Bearer` · role: `ADMIN` or `OWNER`
    """
    _require_user(ctx)
    await IdentityService(session).require_admin(ctx.user.id, org_id)
    billing_svc = BillingService(session)
    url = await billing_svc.create_portal_session(
        org_id=org_id,
        return_url=body.return_url,
    )
    return PortalResponse(portal_url=url)


# ---------------------------------------------------------------------------
# Static endpoint — /subscriptions/plans (no org context)
# ---------------------------------------------------------------------------


@plans_router.get("/plans", response_model=list[PlanInfo])
async def get_plans(
    ctx: ApiContext = Depends(get_api_context),
) -> list[PlanInfo]:
    """Return all available plans with their limits and pricing.

    Auth: `Bearer`
    """
    _require_user(ctx)
    return [
        PlanInfo(
            name=plan.value,
            included_events=cfg.included_events,
            monitoring_allowed=cfg.monitoring_allowed,
            max_members=cfg.max_members,
            pay_as_you_go=cfg.pay_as_you_go,
            monthly_price_cents=cfg.monthly_price_cents,
            overage_unit_price=plan_pricing(plan)["unit_price"],
        )
        for plan, cfg in PLAN_LIMITS.items()
        if plan != SubscriptionPlan.DEVELOPMENT
    ]
