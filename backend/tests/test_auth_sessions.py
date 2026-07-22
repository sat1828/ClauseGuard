import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database import AsyncSessionLocal
from app.models import User
from sqlalchemy import select


async def _register(client, email="auth_flow@example.com", password="testpass123"):
    r = await client.post("/api/auth/register", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.asyncio
async def test_register_returns_both_tokens():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tokens = await _register(client, "both_tokens@example.com")
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["access_token"] != tokens["refresh_token"]


@pytest.mark.asyncio
async def test_refresh_issues_new_access_token_and_rotates_refresh_token():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tokens = await _register(client, "rotate_test@example.com")

        r = await client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert r.status_code == 200
        new_tokens = r.json()
        assert new_tokens["access_token"] != tokens["access_token"]
        assert new_tokens["refresh_token"] != tokens["refresh_token"]

        # New access token actually works
        r_me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_tokens['access_token']}"})
        assert r_me.status_code == 200


@pytest.mark.asyncio
async def test_old_refresh_token_rejected_after_rotation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tokens = await _register(client, "reuse_test@example.com")

        r1 = await client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert r1.status_code == 200

        # Reusing the ORIGINAL (now-rotated-away) refresh token must fail
        r2 = await client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert r2.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_garbage_token_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/auth/refresh", json={"refresh_token": "not_a_real_token_at_all"})
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_logout_revokes_refresh_token():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tokens = await _register(client, "logout_test@example.com")

        r_logout = await client.post("/api/auth/logout", json={"refresh_token": tokens["refresh_token"]})
        assert r_logout.status_code == 204

        # That refresh token no longer works
        r_refresh = await client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert r_refresh.status_code == 401


@pytest.mark.asyncio
async def test_logout_is_idempotent_and_never_errors_on_unknown_token():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/auth/logout", json={"refresh_token": "totally_made_up_token"})
        assert r.status_code == 204  # no error, even though this token never existed


@pytest.mark.asyncio
async def test_logout_all_revokes_every_session():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tokens1 = await _register(client, "multisession@example.com")
        headers1 = {"Authorization": f"Bearer {tokens1['access_token']}"}

        # Simulate a second device logging in
        r_login2 = await client.post("/api/auth/login", json={"email": "multisession@example.com", "password": "testpass123"})
        tokens2 = r_login2.json()

        r_all = await client.post("/api/auth/logout-all", headers=headers1)
        assert r_all.status_code == 204

        # Both sessions' refresh tokens are now dead
        r1 = await client.post("/api/auth/refresh", json={"refresh_token": tokens1["refresh_token"]})
        r2 = await client.post("/api/auth/refresh", json={"refresh_token": tokens2["refresh_token"]})
        assert r1.status_code == 401
        assert r2.status_code == 401


@pytest.mark.asyncio
async def test_email_verification_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tokens = await _register(client, "verify_flow@example.com")
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        r_me_before = await client.get("/api/auth/me", headers=headers)
        assert r_me_before.json()["email_verified"] is False

        # Pull the real token straight from the DB (email isn't actually
        # sent in tests — SMTP isn't configured, it's logged instead, so we
        # grab it directly to prove the verification endpoint itself works)
        async with AsyncSessionLocal() as db:
            user = await db.scalar(select(User).where(User.email == "verify_flow@example.com"))
            raw_token_hash = user.email_verify_token_hash
            assert raw_token_hash is not None  # a token was generated on register

        # We can't reverse the hash, so instead verify the FULL flow via resend,
        # capturing the raw token by monkey-patching would be needed for a true
        # E2E test — here we confirm the endpoint correctly rejects garbage,
        # and that resend-verification generates a fresh token.
        r_bad = await client.post("/api/auth/verify-email", json={"token": "wrong_token"})
        assert r_bad.status_code == 400

        r_resend = await client.post("/api/auth/resend-verification", headers=headers)
        assert r_resend.status_code == 200
        assert r_resend.json()["status"] == "sent"


@pytest.mark.asyncio
async def test_verify_email_with_real_token_succeeds():
    from app.security import generate_token, hash_token
    from datetime import datetime, timedelta, timezone

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await _register(client, "real_verify@example.com")

        # Simulate what the email link contains by generating a token the
        # same way the app does and writing its hash directly, exactly as
        # _create_email_verification_token does internally.
        raw = generate_token()
        async with AsyncSessionLocal() as db:
            user = await db.scalar(select(User).where(User.email == "real_verify@example.com"))
            user.email_verify_token_hash = hash_token(raw)
            user.email_verify_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
            await db.commit()

        r = await client.post("/api/auth/verify-email", json={"token": raw})
        assert r.status_code == 200

        async with AsyncSessionLocal() as db:
            user = await db.scalar(select(User).where(User.email == "real_verify@example.com"))
            assert user.email_verified is True
            assert user.email_verify_token_hash is None


@pytest.mark.asyncio
async def test_expired_verification_token_rejected():
    from app.security import generate_token, hash_token
    from datetime import datetime, timedelta, timezone

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await _register(client, "expired_verify@example.com")

        raw = generate_token()
        async with AsyncSessionLocal() as db:
            user = await db.scalar(select(User).where(User.email == "expired_verify@example.com"))
            user.email_verify_token_hash = hash_token(raw)
            user.email_verify_expires_at = datetime.now(timezone.utc) - timedelta(hours=1)  # already expired
            await db.commit()

        r = await client.post("/api/auth/verify-email", json={"token": raw})
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_password_reset_request_never_reveals_account_existence():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await _register(client, "reset_flow@example.com")

        r_exists = await client.post("/api/auth/request-password-reset", json={"email": "reset_flow@example.com"})
        r_not_exists = await client.post("/api/auth/request-password-reset", json={"email": "never_registered@example.com"})

        assert r_exists.status_code == 200
        assert r_not_exists.status_code == 200
        assert r_exists.json() == r_not_exists.json()  # identical response either way


@pytest.mark.asyncio
async def test_password_reset_full_flow_and_revokes_sessions():
    from app.security import generate_token, hash_token, verify_password
    from datetime import datetime, timedelta, timezone

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tokens = await _register(client, "full_reset@example.com", password="oldpassword123")

        raw = generate_token()
        async with AsyncSessionLocal() as db:
            user = await db.scalar(select(User).where(User.email == "full_reset@example.com"))
            user.password_reset_token_hash = hash_token(raw)
            user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
            await db.commit()

        r_reset = await client.post(
            "/api/auth/reset-password",
            json={"token": raw, "new_password": "newpassword456"},
        )
        assert r_reset.status_code == 200

        # Old password no longer works
        r_old_login = await client.post("/api/auth/login", json={"email": "full_reset@example.com", "password": "oldpassword123"})
        assert r_old_login.status_code == 401

        # New password works
        r_new_login = await client.post("/api/auth/login", json={"email": "full_reset@example.com", "password": "newpassword456"})
        assert r_new_login.status_code == 200

        # The session that existed BEFORE the reset is dead
        r_old_session = await client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert r_old_session.status_code == 401


@pytest.mark.asyncio
async def test_expired_reset_token_rejected():
    from app.security import generate_token, hash_token
    from datetime import datetime, timedelta, timezone

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await _register(client, "expired_reset@example.com")

        raw = generate_token()
        async with AsyncSessionLocal() as db:
            user = await db.scalar(select(User).where(User.email == "expired_reset@example.com"))
            user.password_reset_token_hash = hash_token(raw)
            user.password_reset_expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
            await db.commit()

        r = await client.post("/api/auth/reset-password", json={"token": raw, "new_password": "whatever123"})
        assert r.status_code == 400


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
