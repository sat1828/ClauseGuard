"""
User ORM Models
================
ClauseGuard uses Clerk for authentication — we do NOT store passwords.
The User table maps Clerk user IDs to our internal user records and usage tracking.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    # Clerk's external user ID — used to look up users from JWT claims
    clerk_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=True)

    # Usage tracking (for rate limiting and analytics)
    total_contracts_analyzed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_api_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class UsageRecord(Base):
    """Per-analysis token and cost tracking for billing and analytics."""

    __tablename__ = "usage_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    contract_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Pipeline stage that consumed these tokens
    pipeline_stage: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Cost in USD — computed from Anthropic's pricing at time of call
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # LangSmith run ID for cross-referencing traces
    langsmith_run_id: Mapped[str] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
