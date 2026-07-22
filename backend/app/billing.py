"""
Stripe billing logic.

Design note: `apply_stripe_event` is a pure-ish async function that takes an
already-parsed event type + object and a DB session. It does NOT touch the
network or verify signatures — that happens in the router, right before
calling this. That split is what lets this be unit tested without needing
real Stripe test-mode credentials or valid webhook signatures (see
tests/test_billing.py).

Scope note: subscription plans (starter/pro) are implemented. One-time
credit packs (spec section 9.2) are NOT implemented — flagging that
honestly rather than shipping a half-working version of it. Subscriptions
cover the core upgrade path; add credit packs later if you actually need
them (the pattern would mirror create_checkout_session with mode="payment").
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import User

logger = logging.getLogger("clauseguard.billing")

PLAN_LIMITS = {
    "free": settings.FREE_PLAN_ANALYSES_LIMIT,
    "starter": settings.STARTER_PLAN_ANALYSES_LIMIT,
    "pro": settings.PRO_PLAN_ANALYSES_LIMIT,
}

PLAN_PRICE_ENV = {
    "starter": settings.STRIPE_PRICE_STARTER,
    "pro": settings.STRIPE_PRICE_PRO,
}


class BillingConfigError(Exception):
    """Raised when a Stripe operation is attempted without the required env vars set."""
    pass


def get_stripe():
    import stripe
    if not settings.STRIPE_SECRET_KEY:
        raise BillingConfigError(
            "STRIPE_SECRET_KEY is not set. Get a free test-mode key at "
            "https://dashboard.stripe.com/test/apikeys"
        )
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def create_checkout_session(user: User, plan: str) -> str:
    """Creates a Stripe Checkout session for a subscription upgrade.
    Returns the checkout URL to redirect the user to."""
    if plan not in PLAN_PRICE_ENV:
        raise ValueError(f"Unknown plan: {plan}")

    price_id = PLAN_PRICE_ENV[plan]
    if not price_id:
        raise BillingConfigError(
            f"No Stripe price ID configured for plan '{plan}'. Set STRIPE_PRICE_{plan.upper()} in .env."
        )

    stripe = get_stripe()

    session_kwargs = dict(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{settings.FRONTEND_URL}/billing?checkout=success",
        cancel_url=f"{settings.FRONTEND_URL}/billing?checkout=canceled",
        metadata={"user_id": user.id, "plan": plan},
        subscription_data={"metadata": {"user_id": user.id, "plan": plan}},
    )
    if user.stripe_customer_id:
        session_kwargs["customer"] = user.stripe_customer_id
    else:
        session_kwargs["customer_email"] = user.email

    session = stripe.checkout.Session.create(**session_kwargs)
    return session.url


async def apply_stripe_event(event_type: str, obj: dict, db: AsyncSession) -> None:
    """Applies the business-logic effect of a verified Stripe webhook event.
    Unknown event types are logged and ignored, not errors — Stripe sends
    many event types we don't need to react to."""

    if event_type == "checkout.session.completed":
        metadata = obj.get("metadata") or {}
        user_id = metadata.get("user_id")
        plan = metadata.get("plan")
        if not user_id or not plan:
            logger.warning(f"checkout.session.completed missing metadata: {obj.get('id')}")
            return
        user = await db.get(User, user_id)
        if not user:
            logger.warning(f"checkout.session.completed for unknown user_id: {user_id}")
            return

        user.plan = plan
        user.analyses_limit = PLAN_LIMITS.get(plan, user.analyses_limit)
        user.subscription_status = "active"
        if obj.get("customer"):
            user.stripe_customer_id = obj["customer"]
        if obj.get("subscription"):
            user.stripe_subscription_id = obj["subscription"]
        await db.commit()
        logger.info(f"User {user_id} upgraded to plan '{plan}'.")

    elif event_type == "customer.subscription.deleted":
        subscription_id = obj.get("id")
        user = await db.scalar(select(User).where(User.stripe_subscription_id == subscription_id))
        if not user:
            return
        user.plan = "free"
        user.analyses_limit = PLAN_LIMITS["free"]
        user.subscription_status = "canceled"
        user.stripe_subscription_id = None
        await db.commit()
        logger.info(f"User {user.id} downgraded to free (subscription deleted).")

    elif event_type == "invoice.paid":
        subscription_id = obj.get("subscription")
        if not subscription_id:
            return
        user = await db.scalar(select(User).where(User.stripe_subscription_id == subscription_id))
        if not user:
            return
        # Monthly renewal successfully paid — reset the usage counter.
        user.analyses_used = 0
        user.subscription_status = "active"
        await db.commit()
        logger.info(f"User {user.id} usage reset on renewal.")

    elif event_type == "invoice.payment_failed":
        subscription_id = obj.get("subscription")
        if not subscription_id:
            return
        user = await db.scalar(select(User).where(User.stripe_subscription_id == subscription_id))
        if not user:
            return
        user.subscription_status = "past_due"
        await db.commit()
        logger.warning(
            f"User {user.id} payment failed — marked past_due. "
            f"(No email is sent — this backend has no email service configured.)"
        )

    else:
        logger.debug(f"Ignoring unhandled Stripe event type: {event_type}")
