"""
Central config. Everything secret comes from environment variables.
Nothing here is a real secret — .env is gitignored, .env.example has placeholders only.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Auth
    JWT_SECRET: str = "CHANGE_ME_INSECURE_DEV_ONLY"
    JWT_ALGORITHM: str = "HS256"
    # Short-lived on purpose — refresh tokens (below) are what makes this
    # safe to keep short. A 7-day access token with no revocation mechanism
    # (the previous version of this file) is a real gap: steal the token,
    # own the session for a week, no way to cut it off.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Email verification / password reset
    REQUIRE_EMAIL_VERIFICATION: bool = False  # off by default so it works with zero SMTP setup
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30

    # SMTP (optional — free tier providers work fine: Gmail app passwords,
    # Brevo, etc. If unset, emails are logged instead of sent, so the app
    # still works out of the box without any email setup at all.)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@clauseguard.local"
    SMTP_USE_TLS: bool = True

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./clauseguard.db"

    # Storage (local disk stands in for S3 — same interface, swap later)
    STORAGE_ROOT: str = "./storage/uploads"

    # Set STORAGE_BACKEND=s3 to switch to S3-compatible object storage
    # (Cloudflare R2, AWS S3, Backblaze B2, etc.) instead of local disk.
    # R2 is the free-tier recommendation — see backend/README.md.
    STORAGE_BACKEND: str = "local"  # "local" | "s3"
    S3_BUCKET: str = ""
    S3_ENDPOINT_URL: str = ""  # required for R2/non-AWS providers, blank = real AWS S3
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    S3_REGION: str = "auto"  # R2 uses "auto"

    # Groq (free tier) — https://console.groq.com/keys
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_MAX_RETRIES: int = 3
    GROQ_TIMEOUT_SECONDS: int = 30

    # Analysis limits (see SKILL notes in README re: why these exist)
    MAX_FILE_SIZE_MB: int = 25
    MAX_PAGES: int = 200
    MAX_CLAUSES_PER_DOCUMENT: int = 60
    MIN_EXTRACTED_WORDS: int = 50
    MAX_CONCURRENT_ANALYSES: int = 5

    # Plans
    FREE_PLAN_ANALYSES_LIMIT: int = 3
    STARTER_PLAN_ANALYSES_LIMIT: int = 20
    # "Unlimited" in the original spec is a real business-model risk (see
    # README audit note) — Pro gets a high but finite fair-use ceiling
    # instead of true unlimited, which has no cost floor against LLM spend.
    PRO_PLAN_ANALYSES_LIMIT: int = 500

    # Stripe (test mode is free — get keys at https://dashboard.stripe.com/test/apikeys)
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_STARTER: str = ""
    STRIPE_PRICE_PRO: str = ""
    FRONTEND_URL: str = "http://127.0.0.1:5173"

    # OCR (optional — feature-detected at runtime, see parsing.py)
    OCR_ENABLED: bool = True
    OCR_CHAR_THRESHOLD_PER_PAGE: int = 100


settings = Settings()
