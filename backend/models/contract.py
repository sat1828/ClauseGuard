"""
Contract ORM Models
====================
Persistent state for contracts, their analysis results, and processing status.

Schema design decisions:
- JSONB columns for extracted_clauses / risk_assessments / alternatives /
  missing_clauses: these are read-atomically and never queried column-by-column.
  Storing as JSONB avoids a 4-table JOIN on every analysis read and matches the
  Pydantic FullAnalysisResult structure exactly.
- Separate ContractStatus table-less enum: status transitions are linear
  (PENDING → PROCESSING → COMPLETE | FAILED), so a simple string column suffices.
- ClauseResult rows are stored both in JSONB (fast full-read) and as a separate
  table (for future per-clause queries, export, and analytics).
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)

    # Pipeline status
    # PENDING    → file received, pipeline not started
    # PROCESSING → pipeline running
    # COMPLETE   → FullAnalysisResult available
    # FAILED     → pipeline error, error_message populated
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="PENDING", index=True
    )
    progress_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current_stage: Mapped[str] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    # Denormalized analysis summary (for dashboard listing — avoids JOIN)
    contract_type: Mapped[str] = mapped_column(String(50), nullable=True)
    overall_risk_score: Mapped[float] = mapped_column(Float, nullable=True)
    critical_count: Mapped[int] = mapped_column(Integer, nullable=True)
    high_count: Mapped[int] = mapped_column(Integer, nullable=True)
    medium_count: Mapped[int] = mapped_column(Integer, nullable=True)
    low_count: Mapped[int] = mapped_column(Integer, nullable=True)

    # Full analysis stored as JSONB — matches FullAnalysisResult Pydantic schema
    full_analysis: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=True)

    # Pinecone namespace for this contract's embeddings
    # Format: "contract_{contract_id}" — allows cleanup on DELETE
    pinecone_namespace: Mapped[str] = mapped_column(String(100), nullable=True)

    analysis_duration_seconds: Mapped[float] = mapped_column(Float, nullable=True)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    # Relationships
    clauses: Mapped[list["ClauseResult"]] = relationship(
        "ClauseResult", back_populates="contract", cascade="all, delete-orphan"
    )
    chat_messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="contract", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Contract id={self.id} filename={self.filename} status={self.status}>"


class ClauseResult(Base):
    """
    Individual clause extraction + risk assessment result.
    Stored both here (for analytics) and in Contract.full_analysis JSONB (for fast reads).
    """

    __tablename__ = "clause_results"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    contract_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    clause_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    page_start: Mapped[int] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int] = mapped_column(Integer, nullable=True)
    relevant_text: Mapped[str] = mapped_column(Text, nullable=True)
    plain_english_summary: Mapped[str] = mapped_column(Text, nullable=True)
    why_it_matters: Mapped[str] = mapped_column(Text, nullable=True)
    chunk_id: Mapped[str] = mapped_column(String(36), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    contract: Mapped["Contract"] = relationship("Contract", back_populates="clauses")

    __table_args__ = (
        UniqueConstraint("contract_id", "clause_type", "chunk_id", name="uq_clause_per_chunk"),
    )


class ChatMessage(Base):
    """Persisted chat history for a contract's Q&A session."""

    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    contract_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=True)
    confidence: Mapped[str] = mapped_column(String(30), nullable=True)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )

    contract: Mapped["Contract"] = relationship("Contract", back_populates="chat_messages")
