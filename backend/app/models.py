import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Numeric, Boolean, DateTime, ForeignKey, Text, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    # Naive on purpose: SQLite's DateTime(timezone=True) doesn't actually
    # preserve tzinfo on round-trip (it comes back naive regardless of what
    # went in), so a freshly created aware datetime silently fails to
    # compare against one just read from the DB. Keeping this naive-but-UTC
    # everywhere avoids that trap. If you migrate to Postgres, this still
    # works correctly — Postgres DOES preserve tzinfo, and naive-UTC compares
    # fine against aware-UTC there too as long as both sides stay consistent.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    plan: Mapped[str] = mapped_column(String(20), default="free")  # free, starter, pro
    analyses_used: Mapped[int] = mapped_column(Integer, default=0)
    analyses_limit: Mapped[int] = mapped_column(Integer, default=3)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subscription_status: Mapped[str] = mapped_column(String(20), default="active")  # active, past_due, canceled

    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verify_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    email_verify_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    password_reset_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    password_reset_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    documents: Mapped[list["Document"]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)  # pdf, docx

    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, processing, complete, failed
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    overall_risk_score: Mapped[float | None] = mapped_column(Numeric(4, 2), nullable=True)
    overall_risk_label: Mapped[str | None] = mapped_column(String(20), nullable=True)

    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_ocr: Mapped[bool] = mapped_column(Boolean, default=False)

    clauses_total: Mapped[int] = mapped_column(Integer, default=0)
    clauses_processed: Mapped[int] = mapped_column(Integer, default=0)
    clauses_failed: Mapped[int] = mapped_column(Integer, default=0)
    partial_analysis: Mapped[bool] = mapped_column(Boolean, default=False)
    truncated: Mapped[bool] = mapped_column(Boolean, default=False)  # hit MAX_CLAUSES_PER_DOCUMENT

    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    owner: Mapped["User"] = relationship(back_populates="documents")
    clauses: Mapped[list["Clause"]] = relationship(back_populates="document", cascade="all, delete-orphan",
                                                     order_by="Clause.clause_index")
    flags: Mapped[list["DocumentFlag"]] = relationship(back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_documents_user_id", "user_id"),
    )


class Clause(Base):
    __tablename__ = "clauses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    clause_index: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)

    clause_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_label: Mapped[str | None] = mapped_column(String(20), nullable=True)
    plain_english_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_safer_language: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(3, 2), nullable=True)
    flags: Mapped[list] = mapped_column(JSON, default=list)

    analysis_failed: Mapped[bool] = mapped_column(Boolean, default=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    document: Mapped["Document"] = relationship(back_populates="clauses")

    __table_args__ = (
        Index("ix_clauses_document_id", "document_id"),
    )


class DocumentFlag(Base):
    __tablename__ = "document_flags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    flag_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)  # warning, critical
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    affected_clause_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("clauses.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    document: Mapped["Document"] = relationship(back_populates="flags")

    __table_args__ = (
        Index("ix_document_flags_document_id", "document_id"),
    )


class RefreshToken(Base):
    """One row per active session. Storing the HASH of the token (not the
    token itself) means a database leak doesn't hand out working sessions —
    same principle as password hashing. Revoking a session (logout,
    logout-everywhere, or a password reset) is just flipping `revoked`."""
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="refresh_tokens")

    __table_args__ = (
        Index("ix_refresh_tokens_user_id", "user_id"),
    )


class StripeEvent(Base):
    """Log of every processed Stripe webhook event, keyed by Stripe's own
    event ID. Stripe retries webhook delivery on anything but a 2xx — this
    table is what makes double-delivery a no-op instead of double-crediting
    a user's account."""
    __tablename__ = "stripe_events"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)  # Stripe event ID, e.g. evt_...
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
