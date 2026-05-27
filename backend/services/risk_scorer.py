"""
Risk Scorer — Stage 4
=======================
CRITICAL: temperature=0 is MANDATORY and enforced here. Never change it.
Two runs on the same clause must produce identical output.
"""

import time
import uuid

import structlog
from langsmith import traceable
from tenacity import retry, stop_after_attempt, wait_exponential

from config import get_settings
from prompts.risk_scoring import build_risk_scoring_prompt
from schemas.analysis import ClauseExtractionResult, RiskAssessment
from services.llm_utils import get_anthropic_client, parse_json_response

logger = structlog.get_logger(__name__)
settings = get_settings()


@retry(
    stop=stop_after_attempt(settings.LLM_RETRY_MAX_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
@traceable(
    name="score_clause_risk",
    tags=["risk-scoring"],
    metadata={"pipeline_stage": "4_risk_scoring"},
)
async def _score_single_clause(
    clause: ClauseExtractionResult,
    contract_type: str,
    jurisdiction: str,
    contract_id: str,
) -> RiskAssessment:
    """Score a single clause. ENFORCES temperature=0."""
    client = get_anthropic_client()
    clause_id = str(uuid.uuid4())

    system_prompt, user_prompt = build_risk_scoring_prompt(
        clause_type=clause.clause_type,
        clause_id=clause_id,
        clause_text=clause.relevant_text,
        contract_type=contract_type,
        jurisdiction=jurisdiction,
    )

    response = await client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=1024,
        temperature=0,  # MANDATORY: determinism is a correctness requirement
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    content = response.content[0].text.strip()
    parsed = parse_json_response(content)
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected dict from risk scorer, got {type(parsed)}")

    parsed["clause_id"] = clause_id
    parsed["clause_type"] = clause.clause_type

    assessment = RiskAssessment.model_validate(parsed)

    if assessment.source_text and len(assessment.source_text) > 20:
        if not _is_text_grounded(assessment.source_text, clause.relevant_text):
            logger.warning(
                "ungrounded_source_text",
                clause_type=clause.clause_type,
                contract_id=contract_id,
            )

    return assessment


def _is_text_grounded(source_text: str, original_clause: str) -> bool:
    """Fuzzy check: source_text should overlap 60%+ with clause text."""
    source_words = set(source_text.lower().split())
    clause_words = set(original_clause.lower().split())
    if not source_words:
        return False
    return len(source_words & clause_words) / len(source_words) >= 0.6


async def score_clauses(
    clauses: list[ClauseExtractionResult],
    contract_type: str,
    jurisdiction: str,
    contract_id: str,
) -> list[RiskAssessment]:
    """Stage 4: Score all identified clauses."""
    SKIP_TYPES = {"DEFINITIONS"}
    scored_clauses = [
        c for c in clauses
        if not c.low_confidence and c.clause_type not in SKIP_TYPES
    ]

    logger.info(
        "scoring_clauses",
        contract_id=contract_id,
        total=len(clauses),
        scoring=len(scored_clauses),
        skipped=len(clauses) - len(scored_clauses),
    )

    assessments: list[RiskAssessment] = []
    start_time = time.time()

    for clause in scored_clauses:
        try:
            assessment = await _score_single_clause(
                clause, contract_type, jurisdiction, contract_id
            )
            assessments.append(assessment)
        except Exception as e:
            logger.error(
                "clause_scoring_failed",
                clause_type=clause.clause_type,
                contract_id=contract_id,
                error=str(e),
            )

    assessments.sort(key=lambda a: a.risk_score, reverse=True)

    logger.info(
        "risk_scoring_complete",
        contract_id=contract_id,
        scored=len(assessments),
        duration=round(time.time() - start_time, 2),
    )
    return assessments


def compute_overall_risk_score(assessments: list[RiskAssessment]) -> float:
    """Weighted average: CRITICAL=3x, HIGH=2x, MEDIUM=1x, LOW=0.5x."""
    if not assessments:
        return 0.0
    WEIGHTS = {"CRITICAL": 3.0, "HIGH": 2.0, "MEDIUM": 1.0, "LOW": 0.5}
    weighted_sum = sum(
        a.risk_score * WEIGHTS.get(a.risk_level, 1.0) for a in assessments
    )
    weight_total = sum(WEIGHTS.get(a.risk_level, 1.0) for a in assessments)
    return round(min(10.0, max(0.0, weighted_sum / weight_total)), 1)
