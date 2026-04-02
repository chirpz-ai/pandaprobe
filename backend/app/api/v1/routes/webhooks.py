"""Stripe webhook handler.

Receives events from Stripe and dispatches them to the billing
service for subscription lifecycle management.  The endpoint
bypasses normal auth -- it validates the Stripe webhook signature.
"""

import stripe
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.engine import get_db_session
from app.logging import logger
from app.registry.settings import settings
from app.services.billing_service import BillingService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_HANDLED_EVENTS = {
    "checkout.session.completed",
    "invoice.paid",
    "invoice.payment_failed",
    "customer.subscription.updated",
    "customer.subscription.deleted",
}


@router.post("/stripe")
async def stripe_webhook(request: Request) -> JSONResponse:
    """Receive and process Stripe webhook events.

    No Bearer auth -- the request is verified using the Stripe
    webhook signature in the ``Stripe-Signature`` header.
    """
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET,
        )
    except ValueError:
        logger.warning("stripe_webhook_invalid_payload")
        return JSONResponse(status_code=400, content={"detail": "Invalid payload"})
    except stripe.SignatureVerificationError:
        logger.warning("stripe_webhook_invalid_signature")
        return JSONResponse(status_code=400, content={"detail": "Invalid signature"})

    event_type = event["type"]
    event_data = event["data"]

    if event_type not in _HANDLED_EVENTS:
        return JSONResponse(status_code=200, content={"received": True})

    async for session in get_db_session():
        billing_svc = BillingService(session)

        try:
            match event_type:
                case "checkout.session.completed":
                    await billing_svc.handle_checkout_completed(event_data)
                case "invoice.paid":
                    await billing_svc.handle_invoice_paid(event_data)
                case "invoice.payment_failed":
                    await billing_svc.handle_invoice_payment_failed(event_data)
                case "customer.subscription.updated":
                    await billing_svc.handle_subscription_updated(event_data)
                case "customer.subscription.deleted":
                    await billing_svc.handle_subscription_deleted(event_data)
        except Exception:
            logger.exception("stripe_webhook_handler_error", event_type=event_type)
            return JSONResponse(status_code=500, content={"detail": "Internal error"})

    logger.info("stripe_webhook_processed", event_type=event_type)
    return JSONResponse(status_code=200, content={"received": True})
