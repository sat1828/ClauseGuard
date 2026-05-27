"""
Integration Tests — Full Pipeline (no real API calls)
Run: pytest tests/test_pipeline.py -v
"""

import os
import tempfile
import uuid
from datetime import datetime, timezone

import pytest

from schemas.analysis import (
    AlternativeClause, ClauseExtractionResult, ContractTypeResult,
    FullAnalysisResult, MissingClause, RiskAssessment,
)
from services.chunker import chunk_document
from services.document_parser import ParsedDocument, PageBlock, extract_defined_terms
from services.missing_clause_detector import detect_missing_clauses
from services.risk_scorer import compute_overall_risk_score


def make_parsed_doc(text: str) -> ParsedDocument:
    lines = text.strip().split("\n")
    blocks = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        is_heading = (
            stripped.isupper() or
            (len(stripped) < 80 and stripped.startswith(tuple("123456789")) and ". " in stripped)
        )
        blocks.append(PageBlock(
            page_num=max(1, i // 10),
            text=stripped,
            is_heading=is_heading,
            font_size=14 if is_heading else 11,
        ))
    return ParsedDocument(
        blocks=blocks, defined_terms={},
        total_pages=max(1, len(blocks) // 10),
        raw_text=text, file_type="txt",
    )


EMPLOYMENT_TEXT = """
EMPLOYMENT AGREEMENT

1. COMPENSATION
The Company shall pay Employee a gross annual salary of INR 28,00,000.

2. INTELLECTUAL PROPERTY ASSIGNMENT
Employee hereby irrevocably assigns to the Company all right, title, and interest
in and to all inventions whether or not created during working hours.

3. NON-COMPETE
During employment and for two years thereafter Employee shall not engage in any
competing business anywhere in India.

4. TERMINATION
The Company may terminate immediately for gross misconduct. Employee shall give
90 days written notice upon resignation.

5. GOVERNING LAW
This Agreement is governed by the laws of India.
"""

SAAS_TEXT = """
SAAS SUBSCRIPTION AGREEMENT

1. PAYMENT TERMS
Customer shall pay USD 24,000 annually payable in advance.

2. AUTO-RENEWAL
This Agreement automatically renews for successive one-year terms unless cancelled
90 days prior to renewal date.

3. DATA PROTECTION
Provider processes Customer data in accordance with applicable data protection law.

4. LIMITATION OF LIABILITY
Provider aggregate liability shall not exceed fees paid in prior 12 months.
"""

NDA_TEXT = """
NON-DISCLOSURE AGREEMENT

1. DEFINITIONS
Confidential Information means any data disclosed by Disclosing Party designated confidential.

2. CONFIDENTIALITY
Receiving Party shall hold all Confidential Information in strict confidence.

3. GOVERNING LAW
This Agreement is governed by the laws of India.

4. DISPUTE RESOLUTION
Disputes shall be settled by arbitration in Bengaluru.
"""


# ─── Chunker tests ───────────────────────────────────────────────────────────

def test_chunking_employment_produces_chunks():
    doc = make_parsed_doc(EMPLOYMENT_TEXT)
    chunks = chunk_document(doc, contract_type="EMPLOYMENT")
    assert len(chunks) > 0
    assert all(c.token_count > 0 for c in chunks)
    assert all(c.token_count <= 880 for c in chunks)


def test_chunking_preserves_ip_clause_text():
    doc = make_parsed_doc(EMPLOYMENT_TEXT)
    chunks = chunk_document(doc, contract_type="EMPLOYMENT")
    all_text = " ".join(c.text for c in chunks)
    assert "irrevocably assigns" in all_text
    assert "working hours" in all_text


# ─── Missing clause detection ────────────────────────────────────────────────

def test_nda_missing_no_critical_when_complete():
    identified = [
        ClauseExtractionResult(clause_type=ct, relevant_text="Sample.", confidence=0.9,
                               chunk_id=f"c-{ct}")
        for ct in ["CONFIDENTIALITY", "DEFINITIONS", "GOVERNING_LAW", "DISPUTE_RESOLUTION"]
    ]
    missing = detect_missing_clauses(identified, "NDA", "test")
    critical = [m for m in missing if m.severity == "CRITICAL"]
    assert len(critical) == 0


def test_saas_missing_auto_renewal_flagged_critical():
    identified = [
        ClauseExtractionResult(clause_type=ct, relevant_text="Sample.", confidence=0.9,
                               chunk_id=f"c-{ct}")
        for ct in ["PAYMENT_TERMS", "DATA_PROTECTION", "LIMITATION_OF_LIABILITY"]
    ]
    missing = detect_missing_clauses(identified, "SAAS", "test")
    missing_types = [m.clause_type for m in missing]
    assert "AUTO_RENEWAL" in missing_types
    auto = next(m for m in missing if m.clause_type == "AUTO_RENEWAL")
    assert auto.severity == "CRITICAL"


def test_employment_missing_payment_is_critical():
    identified = [
        ClauseExtractionResult(clause_type="NON_COMPETE", relevant_text="No compete 2 years.",
                               confidence=0.95, chunk_id="c-nc")
    ]
    missing = detect_missing_clauses(identified, "EMPLOYMENT", "test")
    missing_types = [m.clause_type for m in missing]
    assert "PAYMENT_TERMS" in missing_types
    pay = next(m for m in missing if m.clause_type == "PAYMENT_TERMS")
    assert pay.severity == "CRITICAL"


def test_unknown_type_no_missing():
    missing = detect_missing_clauses([], "UNKNOWN", "test")
    assert missing == []


# ─── Risk score computation ──────────────────────────────────────────────────

def make_ra(level: str, score: int) -> RiskAssessment:
    return RiskAssessment(
        clause_id=str(uuid.uuid4()),
        clause_type="TEST",
        risk_level=level,
        risk_score=score,
        disadvantaged_party="USER",
        plain_english_summary="Test summary here for this clause.",
        why_it_matters="Test why it matters to the user.",
        rubric_scores={k: 1 for k in [
            "scope_breadth","duration","party_asymmetry","enforceability_concern",
            "jurisdiction_risk","financial_exposure","exit_difficulty","standard_market_practice"
        ]},
        confidence=0.9,
        source_text="Test source text from the contract.",
    )


def test_critical_clause_dominates_score():
    assessments = [make_ra("CRITICAL", 9)] + [make_ra("LOW", 1)] * 8
    score = compute_overall_risk_score(assessments)
    assert score >= 4.0
    assert score <= 10.0


def test_all_low_score_stays_low():
    assessments = [make_ra("LOW", 2)] * 10
    score = compute_overall_risk_score(assessments)
    assert score <= 4.0


# ─── FullAnalysisResult schema ───────────────────────────────────────────────

def test_full_analysis_result_validates():
    ra = make_ra("HIGH", 7)
    result = FullAnalysisResult(
        contract_id=str(uuid.uuid4()),
        contract_type=ContractTypeResult(
            contract_type="EMPLOYMENT",
            confidence=0.94,
            reasoning="Employment confirmed.",
            jurisdiction_hint="India",
        ),
        extracted_clauses=[],
        risk_assessments=[ra],
        alternatives=[],
        missing_clauses=[],
        overall_risk_score=7.0,
        critical_count=0,
        high_count=1,
        medium_count=0,
        low_count=0,
        total_clauses_found=1,
        analysis_duration_seconds=12.5,
        pipeline_version="1.0.0",
        analyzed_at=datetime.now(timezone.utc),
    )
    assert result.overall_risk_score == 7.0
    assert result.high_count == 1


def test_full_analysis_rejects_wrong_counts():
    ra = make_ra("HIGH", 7)
    with pytest.raises(Exception):
        FullAnalysisResult(
            contract_id=str(uuid.uuid4()),
            contract_type=ContractTypeResult(
                contract_type="EMPLOYMENT", confidence=0.9, reasoning="Test"),
            extracted_clauses=[],
            risk_assessments=[ra],
            alternatives=[],
            missing_clauses=[],
            overall_risk_score=7.0,
            critical_count=0,
            high_count=0,   # WRONG — should be 1
            medium_count=0,
            low_count=0,
            total_clauses_found=1,
            analysis_duration_seconds=10.0,
            pipeline_version="1.0.0",
            analyzed_at=datetime.now(timezone.utc),
        )


# ─── Parser + defined terms ──────────────────────────────────────────────────

def test_parse_txt_via_parse_document():
    from services.document_parser import parse_document
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(EMPLOYMENT_TEXT)
        tmp = f.name
    try:
        result = parse_document(tmp)
        assert len(result.blocks) > 0
        assert result.file_type == "txt"
        assert "salary" in result.raw_text.lower()
    finally:
        os.unlink(tmp)


def test_defined_term_extraction():
    text = '''
    "Confidential Information" means any technical or business data disclosed by the Disclosing Party.
    "Term" means the period from the Effective Date to the termination date.
    '''
    terms = extract_defined_terms(text)
    assert "Confidential Information" in terms
    assert "Term" in terms


# ─── Sample contract files ───────────────────────────────────────────────────

def test_sample_nda_parses():
    from services.document_parser import parse_document
    p = os.path.join(os.path.dirname(__file__),
                     "..", "evaluation", "test_contracts", "sample_nda.txt")
    if not os.path.exists(p):
        pytest.skip("sample_nda.txt not found")
    result = parse_document(p)
    assert len(result.blocks) > 5
    assert "Confidential Information" in result.raw_text


def test_sample_employment_parses():
    from services.document_parser import parse_document
    p = os.path.join(os.path.dirname(__file__),
                     "..", "evaluation", "test_contracts", "sample_employment.txt")
    if not os.path.exists(p):
        pytest.skip("sample_employment.txt not found")
    result = parse_document(p)
    assert "salary" in result.raw_text.lower()
    assert len(result.blocks) > 5


def test_sample_saas_parses():
    from services.document_parser import parse_document
    p = os.path.join(os.path.dirname(__file__),
                     "..", "evaluation", "test_contracts", "sample_saas.txt")
    if not os.path.exists(p):
        pytest.skip("sample_saas.txt not found")
    result = parse_document(p)
    assert "auto-renewal" in result.raw_text.lower() or "automatically renew" in result.raw_text.lower()
