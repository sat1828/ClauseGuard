from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, RefreshToken, utcnow
from app.schemas import (
    RegisterRequest, LoginRequest, TokenResponse, UserResponse,
    RefreshRequest, LogoutRequest, VerifyEmailRequest,
    RequestPasswordResetRequest, ResetPasswordRequest,
)
from app.security import (
    hash_password, verify_password, create_access_token,
    generate_token, hash_token,
)
from app.deps import get_current_user
from app.config import settings
from app.email import send_verification_email, send_password_reset_email

router = APIRouter(prefix="/api/auth", tags=["auth"])


async def _issue_tokens(user: User, db: AsyncSession, user_agent: str | None = None) -> TokenResponse:
    access_token = create_access_token(user.id)

    raw_refresh = generate_token()
    refresh_row = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_refresh),
        expires_at=utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        user_agent=(user_agent or "")[:500],
    )
    db.add(refresh_row)
    await db.commit()

    return TokenResponse(access_token=access_token, refresh_token=raw_refresh)


async def _create_email_verification_token(user: User, db: AsyncSession) -> str:
    raw = generate_token()
    user.email_verify_token_hash = hash_token(raw)
    user.email_verify_expires_at = utcnow() + timedelta(
        hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS
    )
    await db.commit()
    return raw


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="An account with this email already exists.")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        plan="free",
        analyses_limit=settings.FREE_PLAN_ANALYSES_LIMIT,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    verify_token = await _create_email_verification_token(user, db)
    send_verification_email(user.email, verify_token, settings.FRONTEND_URL)

    return await _issue_tokens(user, db, request.headers.get("user-agent"))


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")

    if settings.REQUIRE_EMAIL_VERIFICATION and not user.email_verified:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before logging in. Check your inbox for the verification link.",
        )

    return await _issue_tokens(user, db, request.headers.get("user-agent"))


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(payload: RefreshRequest, request: Request, db: AsyncSession = Depends(get_db)):
    token_hash = hash_token(payload.refresh_token)
    row = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))

    if not row or row.revoked or row.expires_at < utcnow():
        # Same error whether the token is missing, expired, or revoked —
        # don't help an attacker distinguish "wrong token" from "stolen but revoked token".
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Refresh token is invalid or expired. Please log in again.")

    user = await db.get(User, row.user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="User no longer exists.")

    # Rotate: revoke the used token, issue a brand new pair. If a stolen
    # refresh token gets used by an attacker after the legitimate user
    # already rotated it, this old-token-reuse is detectable (a nice future
    # enhancement: auto-revoke the whole session family on reuse detection).
    row.revoked = True
    row.last_used_at = utcnow()
    await db.commit()

    return await _issue_tokens(user, db, request.headers.get("user-agent"))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: LogoutRequest, db: AsyncSession = Depends(get_db)):
    token_hash = hash_token(payload.refresh_token)
    row = await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if row:
        row.revoked = True
        await db.commit()
    # No error if the token was already invalid/unknown — logout is idempotent by design.


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Revokes every active session for the current user — e.g. 'log out of all devices'."""
    result = await db.scalars(
        select(RefreshToken).where(RefreshToken.user_id == current_user.id, RefreshToken.revoked == False)  # noqa: E712
    )
    for row in result.all():
        row.revoked = True
    await db.commit()


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/verify-email", status_code=status.HTTP_200_OK)
async def verify_email(payload: VerifyEmailRequest, db: AsyncSession = Depends(get_db)):
    token_hash = hash_token(payload.token)
    user = await db.scalar(select(User).where(User.email_verify_token_hash == token_hash))

    if not user or not user.email_verify_expires_at or user.email_verify_expires_at < utcnow():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="This verification link is invalid or has expired.")

    user.email_verified = True
    user.email_verify_token_hash = None
    user.email_verify_expires_at = None
    await db.commit()
    return {"status": "verified"}


@router.post("/resend-verification", status_code=status.HTTP_200_OK)
async def resend_verification(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.email_verified:
        return {"status": "already_verified"}
    verify_token = await _create_email_verification_token(current_user, db)
    send_verification_email(current_user.email, verify_token, settings.FRONTEND_URL)
    return {"status": "sent"}


@router.post("/request-password-reset", status_code=status.HTTP_200_OK)
async def request_password_reset(payload: RequestPasswordResetRequest, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.email == payload.email))
    # Always return the same response whether or not the email exists —
    # otherwise this endpoint becomes a free "is this email registered?" oracle.
    if user:
        raw = generate_token()
        user.password_reset_token_hash = hash_token(raw)
        user.password_reset_expires_at = utcnow() + timedelta(
            minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
        )
        await db.commit()
        send_password_reset_email(user.email, raw, settings.FRONTEND_URL)

    return {"status": "if_account_exists_email_sent"}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    token_hash = hash_token(payload.token)
    user = await db.scalar(select(User).where(User.password_reset_token_hash == token_hash))

    if not user or not user.password_reset_expires_at or user.password_reset_expires_at < utcnow():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="This password reset link is invalid or has expired.")

    user.hashed_password = hash_password(payload.new_password)
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    await db.commit()

    # A password reset is a strong signal the account may have been
    # compromised — kill every existing session, not just leave them be.
    result = await db.scalars(
        select(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked == False)  # noqa: E712
    )
    for row in result.all():
        row.revoked = True
    await db.commit()

    return {"status": "password_reset"}
