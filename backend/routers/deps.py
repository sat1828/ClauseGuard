"""
Shared FastAPI Dependencies
============================
Centralises authentication and other cross-cutting dependencies so routers
don't import from each other (which creates circular import risk).

Production upgrade path:
- Replace get_current_user_id() with Clerk JWT verification:
  1. Extract Bearer token from Authorization header
  2. Fetch JWKS from CLERK_JWKS_URL
  3. Decode and verify JWT, extract "sub" claim as user_id
  4. Optionally upsert User record to DB on first login
"""

from fastapi import Header, HTTPException
from typing import Optional


async def get_current_user_id(
    authorization: Optional[str] = Header(default=None),
) -> str:
    """
    Extract user ID from request.

    Development mode: returns a fixed user ID.
    Production mode: verifies Clerk JWT from Authorization header.

    To upgrade to real auth, implement Clerk JWT verification here.
    The rest of the codebase will work unchanged — only this function changes.
    """
    # ── Development: fixed user ID ────────────────────────────────────────
    # In development, all requests are attributed to a single test user.
    # This allows testing without Clerk credentials.
    #
    # DO NOT ship to production without implementing real auth below.
    return "dev-user-001"

    # ── Production: Clerk JWT verification ────────────────────────────────
    # Uncomment and implement this block for production:
    #
    # if not authorization or not authorization.startswith("Bearer "):
    #     raise HTTPException(
    #         status_code=401,
    #         detail="Missing or invalid Authorization header",
    #         headers={"WWW-Authenticate": "Bearer"},
    #     )
    # token = authorization.split(" ", 1)[1]
    # try:
    #     from config import get_settings
    #     import httpx
    #     settings = get_settings()
    #     # Fetch JWKS (cache in production)
    #     async with httpx.AsyncClient() as client:
    #         jwks = (await client.get(settings.CLERK_JWKS_URL)).json()
    #     from jose import jwt
    #     payload = jwt.decode(token, jwks, algorithms=["RS256"])
    #     return payload["sub"]  # Clerk user ID
    # except Exception as e:
    #     raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
