from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, StripeEvent
from app.deps import get_current_user
from app.config import settings
from app.billing import create_checkout_session, apply_stripe_event, BillingConfigError, PLAN_LIMITS

router = APIRouter(prefix="/api/billing", tags=["billing"])


class CheckoutRequest(BaseModel):
    plan: str  # "starter" | "pro"


class CheckoutResponse(BaseModel):
    checkout_url: str


class UsageResponse(BaseModel):
    plan: str
    analyses_used: int
    analyses_limit: int
    subscription_status: str


@router.post("/create-checkout-session", response_model=CheckoutResponse)
async def create_checkout(
    payload: CheckoutRequest,
    current_user: User = Depends(get_current_user),
):
    if payload.plan not in ("starter", "pro"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="plan must be 'starter' or 'pro'.")
    try:
        url = create_checkout_session(current_user, payload.plan)
    except BillingConfigError as e:
        # This is a server misconfiguration (missing Stripe keys), not a user error —
        # but we still don't want to leak internals, so keep the message actionable
        # without dumping stack traces to the client.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except Exception as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=f"Stripe error: {e}")

    return CheckoutResponse(checkout_url=url)


@router.post("/webhook", status_code=status.HTTP_200_OK)
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    import stripe

    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="Webhook secret not configured.")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        # Reject unsigned/invalid webhooks with 400 — never process an
        # unverified payload as if it were a real Stripe event.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature.")

    # Idempotency: Stripe retries delivery on anything but a 2xx. If we've
    # already processed this exact event ID, no-op instead of double-applying.
    existing = await db.get(StripeEvent, event["id"])
    if existing and existing.processed:
        return {"status": "already_processed"}

    if not existing:
        record = StripeEvent(id=event["id"], type=event["type"], raw_payload=dict(event))
        db.add(record)
        await db.commit()
    else:
        record = existing

    await apply_stripe_event(event["type"], event["data"]["object"], db)

    record.processed = True
    await db.commit()

    return {"status": "processed"}


@router.get("/usage", response_model=UsageResponse)
async def get_usage(current_user: User = Depends(get_current_user)):
    return UsageResponse(
        plan=current_user.plan,
        analyses_used=current_user.analyses_used,
        analyses_limit=current_user.analyses_limit,
        subscription_status=current_user.subscription_status,
    )
