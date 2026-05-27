"""
Risk Scorer Unit Tests
========================
Tests Pydantic validation, determinism (temperature=0), retry logic.

Run: pytest tests/test_risk_scorer.py -v
"""

import json
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from schemas.analysis import ClauseExtractionResult, RiskAssessment
from services.risk_scorer import (
    _is_text_grounded,
    _score_single_clause,
    compute_overall_risk_score,
    score_clauses,
)


def make_extraction(clause_type: str, text: str, confidence: float = 0.95) -> ClauseExtractionResult:
    return ClauseExtractionResult(
        clause_type=clause_type,
        relevant_text=text,
        confidence=confidence,
        chunk_id="test-chunk-001",
    )


def make_valid_dict(risk_level="LOW", risk_score=2, clause_type="GOVERNING_LAW") -> dict:
    return {
        "clause_id": "test-001",
        "clause_type": clause_type,
        "risk_level": risk_level,
        "risk_score": risk_score,
        "disadvantaged_party": "NEITHER",
        "plain_english_summary": "This clause specifies California law applies to disputes.",
        "why_it_matters": "You must litigate in California courts.",
        "rubric_scores": {k: 1 for k in [
            "scope_breadth","duration","party_asymmetry","enforceability_concern",
            "jurisdiction_risk","financial_exposure","exit_difficulty","standard_market_practice"
        ]},
        "confidence": 0.95,
        "source_text": "This Agreement shall be governed by the laws of California.",
    }


@pytest.mark.asyncio
async def test_standard_governing_law_scores_low():
    with patch("services.risk_scorer.get_anthropic_client") as mock_fn:
        mock_client = AsyncMock()
        mock_fn.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=json.dumps(make_valid_dict("LOW", 2)))]
        mock_client.messages.create = AsyncMock(return_value=mock_msg)

        clause = make_extraction("GOVERNING_LAW",
            "This Agreement shall be governed by the laws of California.")
        result = await _score_single_clause(clause, "NDA", "US", "test-001")

    assert result.risk_level == "LOW"
    assert result.risk_score <= 4


@pytest.mark.asyncio
async def test_broad_ip_assignment_scores_critical():
    d = make_valid_dict("CRITICAL", 9, "IP_ASSIGNMENT")
    d["disadvantaged_party"] = "USER"
    d["rubric_scores"] = {k: 3 for k in d["rubric_scores"]}
    d["source_text"] = "Employee assigns all inventions whether created during working hours or not."

    with patch("services.risk_scorer.get_anthropic_client") as mock_fn:
        mock_client = AsyncMock()
        mock_fn.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=json.dumps(d))]
        mock_client.messages.create = AsyncMock(return_value=mock_msg)

        clause = make_extraction("IP_ASSIGNMENT",
            "Employee hereby irrevocably assigns all inventions including those "
            "created outside working hours.")
        result = await _score_single_clause(clause, "EMPLOYMENT", "India", "test-002")

    assert result.risk_level == "CRITICAL"
    assert result.risk_score >= 7
    assert result.disadvantaged_party == "USER"


@pytest.mark.asyncio
async def test_pydantic_raises_on_malformed():
    with patch("services.risk_scorer.get_anthropic_client") as mock_fn:
        mock_client = AsyncMock()
        mock_fn.return_value = mock_client
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text='{"risk_level": "HIGH"}')]
        mock_client.messages.create = AsyncMock(return_value=mock_msg)

        clause = make_extraction("GOVERNING_LAW", "Governed by Delaware law.")
        with pytest.raises(Exception):
            await _score_single_clause(clause, "NDA", "US", "test-003")


@pytest.mark.asyncio
async def test_retry_succeeds_on_second_attempt():
    valid = json.dumps(make_valid_dict())
    call_count = 0

    async def mock_create(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        msg = MagicMock()
        msg.content = [MagicMock(text='{"bad": "json"}' if call_count == 1 else valid)]
        return msg

    with patch("services.risk_scorer.get_anthropic_client") as mock_fn:
        mock_client = AsyncMock()
        mock_fn.return_value = mock_client
        mock_client.messages.create = mock_create

        clause = make_extraction("GOVERNING_LAW", "Governed by California law.")
        result = await _score_single_clause(clause, "NDA", "US", "test-004")

    assert call_count == 2
    assert result.risk_level == "LOW"


@pytest.mark.asyncio
async def test_determinism_temperature_always_zero():
    """CRITICAL: temperature=0 must be passed in every single call."""
    valid = json.dumps(make_valid_dict("HIGH", 7))
    captured_temps = []

    async def mock_create(*args, **kwargs):
        captured_temps.append(kwargs.get("temperature", -999))
        msg = MagicMock()
        msg.content = [MagicMock(text=valid)]
        return msg

    with patch("services.risk_scorer.get_anthropic_client") as mock_fn:
        mock_client = AsyncMock()
        mock_fn.return_value = mock_client
        mock_client.messages.create = mock_create

        clause = make_extraction("NON_COMPETE",
            "Employee shall not compete for 5 years worldwide.")

        results = []
        for _ in range(3):
            r = await _score_single_clause(clause, "EMPLOYMENT", "India", "test-005")
            results.append(r)

    assert all(t == 0 for t in captured_temps), \
        f"temperature was not 0 in all calls: {captured_temps}"
    risk_levels = [r.risk_level for r in results]
    assert len(set(risk_levels)) == 1, \
        f"Non-deterministic results across 3 runs: {risk_levels}"


def test_overall_score_weighting():
    def make_ra(level, score):
        return RiskAssessment(
            clause_id=str(uuid.uuid4()),
            clause_type="TEST",
            risk_level=level,
            risk_score=score,
            disadvantaged_party="USER",
            plain_english_summary="Test clause summary here.",
            why_it_matters="Test why it matters.",
            rubric_scores={k: 1 for k in [
                "scope_breadth","duration","party_asymmetry","enforceability_concern",
                "jurisdiction_risk","financial_exposure","exit_difficulty","standard_market_practice"
            ]},
            confidence=0.9,
            source_text="Test source text for the clause.",
        )

    assessments = [make_ra("CRITICAL", 9)] + [make_ra("LOW", 1)] * 5
    score = compute_overall_risk_score(assessments)
    assert score >= 4.0, f"CRITICAL clause should push score up, got {score}"
    assert score <= 10.0


def test_overall_score_empty():
    assert compute_overall_risk_score([]) == 0.0


def test_grounding_check_pass():
    assert _is_text_grounded(
        "Employee assigns all inventions to the Company.",
        "Employee assigns all inventions to the Company during employment."
    ) is True


def test_grounding_check_fail():
    assert _is_text_grounded(
        "The non-compete restriction applies for 5 years globally.",
        "Employee assigns all inventions to the Company."
    ) is False


@pytest.mark.asyncio
async def test_definitions_clause_skipped():
    clause = ClauseExtractionResult(
        clause_type="DEFINITIONS",
        relevant_text='"Confidential Information" means any data disclosed.',
        confidence=0.9,
        chunk_id="chunk-001",
    )
    with patch("services.risk_scorer._score_single_clause") as mock_score:
        mock_score.return_value = AsyncMock()
        await score_clauses([clause], "NDA", "US", "test-006")
    mock_score.assert_not_called()


@pytest.mark.asyncio
async def test_low_confidence_skipped():
    clause = ClauseExtractionResult(
        clause_type="NON_COMPETE",
        relevant_text="Some ambiguous text.",
        confidence=0.45,
        chunk_id="chunk-001",
        low_confidence=True,
    )
    with patch("services.risk_scorer._score_single_clause") as mock_score:
        mock_score.return_value = AsyncMock()
        await score_clauses([clause], "EMPLOYMENT", "India", "test-007")
    mock_score.assert_not_called()
