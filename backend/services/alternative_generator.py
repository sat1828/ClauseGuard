"""
Alternative Clause Generator — Stage 5
"""

import time

import structlog
from langsmith import traceable
from tenacity import retry, stop_after_attempt, wait_exponential

from config import get_settings
from prompts.alternative_generation import (
    MEDIUM_TALKING_POINTS_SYSTEM,
    MEDIUM_TALKING_POINTS_USER,
    build_alternative_generation_prompt,
)
from schemas.analysis import AlternativeClause, RiskAssessment
from services.llm_utils import get_anthropic_client, parse_json_response

logger = structlog.get_logger(__name__)
settings = get_settings()


@retry(
    stop=stop_after_attempt(settings.LLM_RETRY_MAX_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
@traceable(
    name="generate_alternative_clause",
    tags=["alternative-generation"],
    metadata={"pipeline_stage": "5_alternative"},
)
async def _generate_alternative(
    assessment: RiskAssessment,
    original_text: str,
    contract_type: str,
    jurisdiction: str,
) -> AlternativeClause:
    client = get_anthropic_client()
    system_prompt, user_prompt = build_alternative_generation_prompt(
        clause_type=assessment.clause_type,
        risk_level=assessment.risk_level,
        original_clause_text=original_text,
        why_it_matters=assessment.why_it_matters,
        contract_type=contract_type,
    )

    response = await client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=2048,
        temperature=0.1,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    content = response.content[0].text.strip()
    parsed = parse_json_response(content)
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected dict from alternative generator, got {type(parsed)}")

    if "original_clause_text" not in parsed:
        parsed["original_clause_text"] = original_text

    return AlternativeClause.model_validate(parsed)


async def _generate_talking_points(
    assessment: RiskAssessment,
    original_text: str,
) -> list[str]:
    """Generate 3 negotiation talking points for MEDIUM clauses."""
    client = get_anthropic_client()
    user_prompt = MEDIUM_TALKING_POINTS_USER.format(
        clause_type=assessment.clause_type,
        why_it_matters=assessment.why_it_matters,
        clause_text=original_text[:500],
    )

    try:
        response = await client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=512,
            temperature=0.1,
            system=MEDIUM_TALKING_POINTS_SYSTEM,
            messages=[{"role": "user", "content": user_prompt}],
        )
        content = response.content[0].text.strip()
        parsed = parse_json_response(content)
        if isinstance(parsed, list) and len(parsed) >= 3:
            return parsed[:3]
    except Exception:
        pass

    return [
        "I would like to discuss the scope of this clause before signing.",
        "Could we add a mutual obligation so both parties are equally bound by this provision?",
        "I would prefer to include a clear time limitation on this obligation.",
    ]


async def generate_alternatives(
    assessments: list[RiskAssessment],
    clause_texts: dict[str, str],
    contract_type: str,
    jurisdiction: str,
    contract_id: str,
) -> list[AlternativeClause]:
    """Stage 5: Generate alternatives for HIGH/CRITICAL, talking points for MEDIUM."""
    alternatives: list[AlternativeClause] = []
    start_time = time.time()

    high_critical = [a for a in assessments if a.risk_level in ("HIGH", "CRITICAL")]
    medium = [a for a in assessments if a.risk_level == "MEDIUM"]

    logger.info(
        "generating_alternatives",
        contract_id=contract_id,
        high_critical=len(high_critical),
        medium=len(medium),
    )

    for assessment in high_critical:
        original_text = clause_texts.get(assessment.clause_type, assessment.source_text)
        try:
            alt = await _generate_alternative(
                assessment, original_text, contract_type, jurisdiction
            )
            alternatives.append(alt)
        except Exception as e:
            logger.error(
                "alternative_generation_failed",
                clause_type=assessment.clause_type,
                contract_id=contract_id,
                error=str(e),
            )

    for assessment in medium:
        original_text = clause_texts.get(assessment.clause_type, assessment.source_text)
        try:
            points = await _generate_talking_points(assessment, original_text)
            alternatives.append(
                AlternativeClause(
                    original_clause_text=original_text,
                    replacement_clause_text="",
                    what_changed="Medium-risk clause. Negotiation talking points provided below.",
                    negotiation_points=points[:3],
                    protection_improved=assessment.why_it_matters,
                )
            )
        except Exception as e:
            logger.warning(
                "talking_points_failed",
                clause_type=assessment.clause_type,
                contract_id=contract_id,
                error=str(e),
            )

    logger.info(
        "alternatives_complete",
        contract_id=contract_id,
        count=len(alternatives),
        duration=round(time.time() - start_time, 2),
    )
    return alternatives
