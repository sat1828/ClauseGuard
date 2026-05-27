"""
Contract Classifier — Stage 0
================================
Determines contract type before any other pipeline stage.
Accuracy target: 93%+ across 6 types on 30+ real contracts.
"""

import time
from typing import Optional

import structlog
from langsmith import traceable
from tenacity import retry, stop_after_attempt, wait_exponential

from config import get_settings
from prompts.contract_type import build_contract_type_prompt
from schemas.analysis import ContractTypeResult
from services.llm_utils import get_anthropic_client, parse_json_response

logger = structlog.get_logger(__name__)
settings = get_settings()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
@traceable(
    name="classify_contract",
    tags=["contract-classification"],
    metadata={"pipeline_stage": "0_classification"},
)
async def classify_contract(
    raw_text: str,
    contract_id: str,
) -> ContractTypeResult:
    """
    Stage 0: Classify contract type using Claude.
    Returns UNKNOWN if confidence < CLASSIFIER_CONFIDENCE_THRESHOLD.
    """
    client = get_anthropic_client()
    system_prompt, user_prompt = build_contract_type_prompt(raw_text)
    start_time = time.time()

    logger.info("classifying_contract", contract_id=contract_id, text_length=len(raw_text))

    response = await client.messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=512,
        temperature=0,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    duration = time.time() - start_time
    content = response.content[0].text.strip()

    parsed = parse_json_response(content)
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected dict from classifier, got {type(parsed)}")

    result = ContractTypeResult.model_validate(parsed)

    if result.confidence < settings.CLASSIFIER_CONFIDENCE_THRESHOLD:
        logger.warning(
            "classification_low_confidence",
            contract_id=contract_id,
            detected=result.contract_type,
            confidence=result.confidence,
        )
        return ContractTypeResult(
            contract_type="UNKNOWN",
            confidence=result.confidence,
            reasoning=f"Low confidence ({result.confidence:.2f}). Original guess: {result.contract_type}. {result.reasoning}",
            jurisdiction_hint=result.jurisdiction_hint,
        )

    logger.info(
        "contract_classified",
        contract_id=contract_id,
        type=result.contract_type,
        confidence=result.confidence,
        jurisdiction=result.jurisdiction_hint,
        duration_ms=round(duration * 1000),
    )
    return result
