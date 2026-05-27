"""
ClauseGuard Backend Configuration
==================================
All settings loaded from environment variables via pydantic-settings.
Uses model_config instead of class Config (Pydantic v2 style).
"""

import os
from functools import lru_cache

import structlog
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = structlog.get_logger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    APP_NAME: str = "ClauseGuard"
    APP_VERSION: str = "1.0.0"
    PIPELINE_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    BACKEND_URL: str = "http://localhost:8000"

    # ── File Upload ───────────────────────────────────────────────────────────
    MAX_FILE_SIZE_MB: int = 10
    SUPPORTED_FILE_TYPES: str = "pdf,docx,txt"
    UPLOAD_DIR: str = "/tmp/clauseguard/uploads"

    # ── Anthropic ─────────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = Field(default="", description="Anthropic API key")
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    CLAUDE_MAX_TOKENS: int = 4096
    CLAUDE_DEFAULT_TEMPERATURE: float = 0.0

    # ── OpenAI (embeddings only) ──────────────────────────────────────────────
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API key")
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_EMBEDDING_DIMENSIONS: int = 1536

    # ── Pinecone ──────────────────────────────────────────────────────────────
    PINECONE_API_KEY: str = Field(default="", description="Pinecone API key")
    PINECONE_ENVIRONMENT: str = Field(default="us-east-1-aws")
    PINECONE_INDEX_NAME: str = "clauseguard-contracts"
    PINECONE_METRIC: str = "cosine"

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://clauseguard:clauseguard_pass@localhost:5432/clauseguard"
    )
    DATABASE_URL_SYNC: str = ""
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30

    # ── LangSmith ────────────────────────────────────────────────────────────
    LANGCHAIN_API_KEY: str = Field(default="", description="LangSmith API key")
    LANGCHAIN_TRACING_V2: str = "true"
    LANGCHAIN_PROJECT: str = "clauseguard-production"
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"

    # ── Clerk ────────────────────────────────────────────────────────────────
    CLERK_SECRET_KEY: str = Field(default="dev-mode")
    CLERK_JWKS_URL: str = "https://api.clerk.dev/v1/jwks"

    # ── Pipeline ─────────────────────────────────────────────────────────────
    CHUNK_MAX_TOKENS: int = 800
    CHUNK_OVERLAP_TOKENS: int = 200
    RAG_TOP_K: int = 5
    RAG_MEMORY_TURNS: int = 6
    CLASSIFIER_CONFIDENCE_THRESHOLD: float = 0.7
    EXTRACTION_CONFIDENCE_THRESHOLD: float = 0.6
    LLM_RETRY_MAX_ATTEMPTS: int = 3

    @field_validator("UPLOAD_DIR")
    @classmethod
    def create_upload_dir(cls, v: str) -> str:
        os.makedirs(v, exist_ok=True)
        return v

    @model_validator(mode="after")
    def derive_sync_url(self) -> "Settings":
        if not self.DATABASE_URL_SYNC:
            self.DATABASE_URL_SYNC = self.DATABASE_URL.replace(
                "postgresql+asyncpg://", "postgresql://"
            )
        return self

    def configure_langsmith(self) -> None:
        """Apply LangSmith env vars — must be called before any LangChain import."""
        if self.LANGCHAIN_API_KEY:
            os.environ["LANGCHAIN_TRACING_V2"] = self.LANGCHAIN_TRACING_V2
            os.environ["LANGCHAIN_PROJECT"] = self.LANGCHAIN_PROJECT
            os.environ["LANGCHAIN_ENDPOINT"] = self.LANGCHAIN_ENDPOINT
            os.environ["LANGCHAIN_API_KEY"] = self.LANGCHAIN_API_KEY

    @property
    def supported_extensions(self) -> list[str]:
        return [f".{ext.strip()}" for ext in self.SUPPORTED_FILE_TYPES.split(",")]

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings singleton."""
    s = Settings()
    s.configure_langsmith()
    return s
