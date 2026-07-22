import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import AsyncSessionLocal
from app.models import User
from app.billing import apply_stripe_event, PLAN_LIMITS
from app.security import hash_password


async def _make_user(db, email="billing_test@example.com", **kwargs):
    user = User(email=email, hashed_password=hash_password("testpass123"), **kwargs)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.mark.asyncio
async def test_checkout_completed_upgrades_plan():
    async with AsyncSessionLocal() as db:
        user = await _make_user(db, email="upgrade_test@example.com")
        await apply_stripe_event(
            "checkout.session.completed",
            {
                "metadata": {"user_id": user.id, "plan": "starter"},
                "customer": "cus_fake123",
                "subscription": "sub_fake123",
            },
            db,
        )
        await db.refresh(user)
        assert user.plan == "starter"
        assert user.analyses_limit == PLAN_LIMITS["starter"]
        assert user.stripe_customer_id == "cus_fake123"
        assert user.stripe_subscription_id == "sub_fake123"
        assert user.subscription_status == "active"


@pytest.mark.asyncio
async def test_checkout_completed_missing_metadata_is_noop():
    async with AsyncSessionLocal() as db:
        user = await _make_user(db, email="noop_test@example.com")
        original_plan = user.plan
        await apply_stripe_event("checkout.session.completed", {"metadata": {}}, db)
        await db.refresh(user)
        assert user.plan == original_plan  # untouched — nothing crashed either


@pytest.mark.asyncio
async def test_subscription_deleted_downgrades_to_free():
    async with AsyncSessionLocal() as db:
        user = await _make_user(
            db, email="downgrade_test@example.com",
            plan="pro", analyses_limit=PLAN_LIMITS["pro"],
            stripe_subscription_id="sub_todelete",
        )
        await apply_stripe_event("customer.subscription.deleted", {"id": "sub_todelete"}, db)
        await db.refresh(user)
        assert user.plan == "free"
        assert user.analyses_limit == PLAN_LIMITS["free"]
        assert user.stripe_subscription_id is None
        assert user.subscription_status == "canceled"


@pytest.mark.asyncio
async def test_invoice_paid_resets_usage():
    async with AsyncSessionLocal() as db:
        user = await _make_user(
            db, email="renewal_test@example.com",
            plan="starter", analyses_used=20, analyses_limit=20,
            stripe_subscription_id="sub_renewal",
        )
        await apply_stripe_event("invoice.paid", {"subscription": "sub_renewal"}, db)
        await db.refresh(user)
        assert user.analyses_used == 0
        assert user.subscription_status == "active"


@pytest.mark.asyncio
async def test_invoice_payment_failed_marks_past_due():
    async with AsyncSessionLocal() as db:
        user = await _make_user(
            db, email="pastdue_test@example.com",
            plan="starter", stripe_subscription_id="sub_failed",
        )
        await apply_stripe_event("invoice.payment_failed", {"subscription": "sub_failed"}, db)
        await db.refresh(user)
        assert user.subscription_status == "past_due"
        assert user.plan == "starter"  # not downgraded on a single failed payment


@pytest.mark.asyncio
async def test_unknown_event_type_is_ignored_not_error():
    async with AsyncSessionLocal() as db:
        # Should simply not raise.
        await apply_stripe_event("some.future.event.type.we.dont.handle", {}, db)


@pytest.mark.asyncio
async def test_webhook_rejects_invalid_signature():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/billing/webhook",
            content=b'{"id": "evt_fake", "type": "checkout.session.completed"}',
            headers={"stripe-signature": "t=1,v1=deadbeef", "content-type": "application/json"},
        )
        # Either 400 (bad signature) or 503 (no webhook secret configured in test env) —
        # both are correct "don't process this" outcomes. Never 200.
        assert r.status_code in (400, 503)


@pytest.mark.asyncio
async def test_checkout_session_requires_valid_plan():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/auth/register", json={"email": "checkout_test@example.com", "password": "testpass123"})
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        r_bad = await client.post(
            "/api/billing/create-checkout-session",
            headers=headers,
            json={"plan": "enterprise_deluxe"},
        )
        assert r_bad.status_code == 400


@pytest.mark.asyncio
async def test_checkout_session_without_stripe_key_returns_clear_error():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/auth/register", json={"email": "checkout_test2@example.com", "password": "testpass123"})
        token = r.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        r_no_config = await client.post(
            "/api/billing/create-checkout-session",
            headers=headers,
            json={"plan": "starter"},
        )
        # No STRIPE_SECRET_KEY/price IDs configured in the test .env — should
        # fail loudly and clearly (503), never silently succeed.
        assert r_no_config.status_code == 503
        assert "stripe" in r_no_config.json()["error"]["message"].lower() or "price" in r_no_config.json()["error"]["message"].lower()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
