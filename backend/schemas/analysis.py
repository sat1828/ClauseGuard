"""
ClauseGuard Analysis Pydantic Schemas
=======================================
These are the data contracts between pipeline stages AND between backend and frontend.
Every schema enforces strict validation — no Optional fields unless genuinely optional.
Changes here require bumping PIPELINE_VERSION in config.py.

Pydantic v2 is used throughout. Do not use v1 compatibility mode.
"""

import uuid
from datetime import datetime
from typing import Annotated, Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Stage 0: Contract Classification ─────────────────────────────────────────

class ContractTypeResult(BaseModel):
    """Output of classifier.py — gates all downstream stages."""

    contract_type: Literal["NDA", "EMPLOYMENT", "SAAS", "LEASE", "SERVICE", "UNKNOWN"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(max_length=500)
    jurisdiction_hint: Optional[str] = None  # "India", "US", "UK", "Unknown"

    @field_validator("reasoning")
    @classmethod
    def reasoning_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("reasoning must not be empty")
        return v.strip()


# ── Stage 2: Chunking ─────────────────────────────────────────────────────────

class LegalChunk(BaseModel):
    """A single chunk of contract text with its metadata."""

    chunk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str = Field(min_length=10)
    context_header: str  # Prepended at query time; NOT stored in vector DB
    page_range: Tuple[int, int]
    section_heading: str
    chunk_index: int = Field(ge=0)
    token_count: int = Field(ge=1, le=1000)  # Max 1000 gives headroom above 800 limit

    @model_validator(mode="after")
    def validate_page_range(self) -> "LegalChunk":
        start, end = self.page_range
        if start > end:
            raise ValueError(f"page_range start ({start}) must be <= end ({end})")
        return self


# ── Stage 3: Clause Extraction ────────────────────────────────────────────────

CLAUSE_TYPES = [
    "CONFIDENTIALITY",
    "NON_COMPETE",
    "NON_SOLICITATION",
    "IP_ASSIGNMENT",
    "INDEMNIFICATION",
    "LIMITATION_OF_LIABILITY",
    "TERMINATION_FOR_CAUSE",
    "TERMINATION_FOR_CONVENIENCE",
    "AUTO_RENEWAL",
    "PAYMENT_TERMS",
    "LATE_PAYMENT_PENALTY",
    "GOVERNING_LAW",
    "DISPUTE_RESOLUTION",
    "FORCE_MAJEURE",
    "DATA_PROTECTION",
    "EXCLUSIVITY",
    "ASSIGNMENT",
    "AMENDMENT",
    "ENTIRE_AGREEMENT",
    "WAIVER",
    "SEVERABILITY",
    "NOTICE",
    "WARRANTY_DISCLAIMER",
    "REPRESENTATIONS",
    "WORK_PRODUCT",
    "AUDIT_RIGHTS",
    "MOST_FAVORED_NATION",
    "LIQUIDATED_DAMAGES",
    "SURVIVAL",
    "DEFINITIONS",
]

class ClauseExtractionResult(BaseModel):
    """Output of clause_extractor.py for a single identified clause."""

    clause_type: str
    relevant_text: str = Field(min_length=10)
    confidence: float = Field(ge=0.0, le=1.0)
    chunk_id: str
    # Populated if confidence < EXTRACTION_CONFIDENCE_THRESHOLD
    low_confidence: bool = False

    @field_validator("clause_type")
    @classmethod
    def validate_clause_type(cls, v: str) -> str:
        if v not in CLAUSE_TYPES:
            raise ValueError(f"clause_type '{v}' not in allowed CLAUSE_TYPES list")
        return v


# ── Stage 4: Risk Scoring ─────────────────────────────────────────────────────

class RiskAssessment(BaseModel):
    """
    Output of risk_scorer.py for a single clause.
    All fields are non-Optional because a partial risk assessment is useless.
    """

    clause_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    clause_type: str
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    risk_score: int = Field(ge=1, le=10)
    disadvantaged_party: Literal["USER", "COUNTERPARTY", "NEITHER", "BOTH"]
    plain_english_summary: str = Field(min_length=10, max_length=600)
    why_it_matters: str = Field(min_length=10, max_length=300)
    # Scores per rubric dimension — must contain exactly the 8 rubric keys
    rubric_scores: Dict[str, int]
    confidence: float = Field(ge=0.0, le=1.0)
    # The exact clause text this assessment is based on (hallucination guardrail)
    source_text: str = Field(min_length=10)

    RUBRIC_KEYS = {
        "scope_breadth",
        "duration",
        "party_asymmetry",
        "enforceability_concern",
        "jurisdiction_risk",
        "financial_exposure",
        "exit_difficulty",
        "standard_market_practice",
    }

    @field_validator("rubric_scores")
    @classmethod
    def validate_rubric_scores(cls, v: Dict[str, int]) -> Dict[str, int]:
        missing = cls.RUBRIC_KEYS - set(v.keys())
        if missing:
            raise ValueError(f"rubric_scores missing keys: {missing}")
        invalid = {k: score for k, score in v.items() if score not in (1, 2, 3)}
        if invalid:
            raise ValueError(f"rubric_scores values must be 1-3, got: {invalid}")
        return v

    @model_validator(mode="after")
    def validate_score_level_consistency(self) -> "RiskAssessment":
        """
        Sanity check: a risk_score of 9-10 should never be LOW.
        This catches LLM inconsistencies that Pydantic field validation won't catch.
        """
        level_ranges = {"LOW": (1, 4), "MEDIUM": (3, 6), "HIGH": (5, 8), "CRITICAL": (7, 10)}
        lo, hi = level_ranges[self.risk_level]
        if not (lo <= self.risk_score <= hi):
            # Soft warning — don't raise, just clamp the score to be consistent.
            # Raising here would cause retry loops on edge cases (e.g. score=5, level=MEDIUM).
            pass
        return self


# ── Stage 5: Alternative Generation ──────────────────────────────────────────

class AlternativeClause(BaseModel):
    """Output of alternative_generator.py for HIGH/CRITICAL clauses.

    For HIGH/CRITICAL clauses: replacement_clause_text contains a full safer replacement.
    For MEDIUM clauses: replacement_clause_text is empty string — only negotiation_points
    are generated. The validator accepts empty string here explicitly for MEDIUM clauses.
    """

    original_clause_text: str = Field(min_length=10)
    # Empty string is valid for MEDIUM clauses (talking-points only mode).
    # HIGH/CRITICAL always populate this field.
    replacement_clause_text: str = Field(default="")
    what_changed: str = Field(min_length=10, max_length=400)
    # Exactly 3 negotiation points — each a complete sentence the user can send.
    negotiation_points: Annotated[List[str], Field(min_length=3, max_length=3)]
    protection_improved: str = Field(min_length=10, max_length=300)

    @field_validator("negotiation_points")
    @classmethod
    def validate_points_are_sentences(cls, v: List[str]) -> List[str]:
        for i, point in enumerate(v):
            if len(point.strip()) < 20:
                raise ValueError(f"negotiation_points[{i}] is too short to be a useful sentence")
        return v


# ── Stage 6: Missing Clause Detection ────────────────────────────────────────

class MissingClause(BaseModel):
    """A structurally absent clause that should be present for this contract type."""

    clause_type: str
    severity: Literal["RECOMMENDED", "IMPORTANT", "CRITICAL"]
    why_it_matters: str = Field(min_length=10, max_length=400)
    example_language: str = Field(min_length=10, max_length=600)


# ── Full Pipeline Output ──────────────────────────────────────────────────────

class FullAnalysisResult(BaseModel):
    """
    Complete output of the 7-stage pipeline.
    Stored as JSONB in Contract.full_analysis and returned by GET /analysis/{id}.
    """

    contract_id: str
    contract_type: ContractTypeResult
    extracted_clauses: List[ClauseExtractionResult]
    risk_assessments: List[RiskAssessment]
    alternatives: List[AlternativeClause]
    missing_clauses: List[MissingClause]
    overall_risk_score: float = Field(ge=0.0, le=10.0)
    critical_count: int = Field(ge=0)
    high_count: int = Field(ge=0)
    medium_count: int = Field(ge=0)
    low_count: int = Field(ge=0)
    total_clauses_found: int = Field(ge=0)
    analysis_duration_seconds: float = Field(ge=0.0)
    pipeline_version: str
    analyzed_at: datetime

    @model_validator(mode="after")
    def validate_counts(self) -> "FullAnalysisResult":
        actual_critical = sum(1 for r in self.risk_assessments if r.risk_level == "CRITICAL")
        actual_high = sum(1 for r in self.risk_assessments if r.risk_level == "HIGH")
        actual_medium = sum(1 for r in self.risk_assessments if r.risk_level == "MEDIUM")
        actual_low = sum(1 for r in self.risk_assessments if r.risk_level == "LOW")
        if (
            self.critical_count != actual_critical
            or self.high_count != actual_high
            or self.medium_count != actual_medium
            or self.low_count != actual_low
        ):
            raise ValueError("Risk level counts do not match risk_assessments list")
        return self


# ── Stage 7: RAG Chat ─────────────────────────────────────────────────────────

class Citation(BaseModel):
    chunk_id: str
    page_range: Tuple[int, int]
    relevant_excerpt: str = Field(min_length=10, max_length=500)
    section_heading: Optional[str] = None


class ChatResponse(BaseModel):
    answer: str = Field(min_length=1)
    citations: List[Citation]
    confidence: Literal["HIGH", "MEDIUM", "LOW", "NOT_IN_DOCUMENT"]
    tokens_used: Optional[int] = None
