import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "access",
        # Without a unique claim, two tokens issued for the same user in the
        # same second (same sub, same exp) encode to the literal same JWT
        # string. Harmless for auth itself, but it breaks the assumption
        # that "refreshed" means "different token" and would make per-token
        # audit logging useless.
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload.get("sub")
    except JWTError:
        return None


# ---- High-entropy random tokens (refresh tokens, password reset, email
# verification). These are NOT user-chosen secrets, so bcrypt (slow by
# design, and truncates at 72 bytes) is the wrong tool — sha256 is correct
# here: fast, no truncation, and the tokens have far more entropy than
# bcrypt's cost factor is meant to defend against in the first place. ----

def generate_token() -> str:
    """Returns a URL-safe random token with ~256 bits of entropy."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
