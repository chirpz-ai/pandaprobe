"""Routes for subscription management and usage information.

All endpoints require a valid Bearer JWT.
"""

from typing import Any
from uuid import UUID

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.context import ApiContext
from app.api.dependencies import get_api_context
from app.infrastructure.db.engine import get_db_session
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
    from app.infrastructure.db.repositories.billing_repo import BillingRepository

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
