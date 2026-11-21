"""Removed plans are invalid; shared paid-plan checkout remains available."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
import stripe

from app.registry.constants import SubscriptionPlan
from app.registry.settings import settings
from app.services.billing_service import BillingService, _resolve_plan_from_price_id


@pytest.mark.parametrize(
    "plan",
    ["PRO", SubscriptionPlan.HOBBY, SubscriptionPlan.ENTERPRISE, SubscriptionPlan.DEVELOPMENT],
)
async def test_checkout_service_rejects_unavailable_plans(plan, monkeypatch):
    service = BillingService(AsyncMock())
    service._repo = AsyncMock()
    create = MagicMock()
    monkeypatch.setattr(stripe.checkout.Session, "create", create)

    with pytest.raises(ValueError, match="Checkout is only available for STARTUP"):
        await service.create_checkout_session(
            uuid4(), plan, success_url="https://example.com/success", cancel_url="https://example.com/cancel"
        )

    create.assert_not_called()
    service._repo.get_subscription_by_org.assert_not_awaited()


@pytest.mark.parametrize(
    ("price_id", "expected"),
    [("price_startup", SubscriptionPlan.STARTUP), ("price_retired_pro", None)],
)
def test_price_resolution_only_recognizes_current_prices(price_id, expected, monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_STARTUP_PRICE_ID", "price_startup")
    assert _resolve_plan_from_price_id(price_id) == expected


def test_pro_is_not_a_subscription_plan():
    with pytest.raises(ValueError):
        SubscriptionPlan("PRO")
