"""
Clause Extractor — Stage 3
============================
Identifies and classifies legal clauses in each chunk.
Batches 5 chunks per API call to reduce cost.
"""

import time
from typing import Optional

import structlog
from langsmith import traceable
from tenacity import retry, stop_after_attempt, wait_exponential

from config import get_settings
from prompts.clause_extraction import build_clause_extraction_prompt
from schemas.analysis import CLAUSE_TYPES, ClauseExtractionResult, LegalChunk
from services.llm_utils import get_anthropic_client, parse_json_response

logger = structlog.get_logger(__name__)
settings = get_settings()

BATCH_SIZE = 5


@traceable(
    name="extract_clauses_batch",
    tags=["clause-extraction"],
    metadata={"pipeline_stage": "3_extraction"},
)
async def _extract_from_batch(
    chunks: list[LegalChunk],
    contract_type: str,
    jurisdiction: str,
    contract_id: str,
) -> list[ClauseExtractionResult]:
    """Extract clauses from a batch of up to 5 chunks."""
    client = get_anthropic_client()
    system_prompt, user_prompt = build_clause_extraction_prompt(
        chunks, contract_type, jurisdiction
    )

    @retry(
        stop=stop_after_attempt(settings.LLM_RETRY_MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    async def _call_with_retry() -> list[ClauseExtractionResult]:
        response = await client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=2048,
            temperature=0,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        content = response.content[0].text.strip()
        parsed = parse_json_response(content)

        if isinstance(parsed, dict):
            parsed = [parsed]
        elif not isinstance(parsed, list):
            raise ValueError(f"Expected list from extractor, got {type(parsed)}")

        results = []
        for item in parsed:
            try:
                if item.get("clause_type") not in CLAUSE_TYPES:
                    logger.warning(
                        "invalid_clause_type",
                        clause_type=item.get("clause_type"),
                        contract_id=contract_id,
                    )
                    continue
                result = ClauseExtractionResult.model_validate(item)
                if result.confidence < settings.EXTRACTION_CONFIDENCE_THRESHOLD:
                    result = result.model_copy(update={"low_confidence": True})
                results.append(result)
            except Exception as e:
                logger.warning(
                    "clause_validation_failed",
                    error=str(e),
                    item=str(item)[:200],
                    contract_id=contract_id,
                )
        return results

    return await _call_with_retry()


async def extract_clauses(
    chunks: list[LegalChunk],
    contract_type: str,
    jurisdiction: str,
    contract_id: str,
) -> list[ClauseExtractionResult]:
    """Stage 3: Extract all clauses from all chunks."""
    all_results: list[ClauseExtractionResult] = []
    total_batches = (len(chunks) + BATCH_SIZE - 1) // BATCH_SIZE
    start_time = time.time()

    logger.info(
        "starting_clause_extraction",
        contract_id=contract_id,
        chunks=len(chunks),
        batches=total_batches,
    )

    for batch_num, i in enumerate(range(0, len(chunks), BATCH_SIZE)):
        batch = chunks[i: i + BATCH_SIZE]
        try:
            batch_results = await _extract_from_batch(
                batch, contract_type, jurisdiction, contract_id
            )
            all_results.extend(batch_results)
        except Exception as e:
            logger.error(
                "batch_extraction_failed",
                batch=batch_num + 1,
                contract_id=contract_id,
                error=str(e),
            )

    deduplicated = _deduplicate_clauses(all_results)
    duration = time.time() - start_time

    logger.info(
        "clause_extraction_complete",
        contract_id=contract_id,
        raw_count=len(all_results),
        deduped_count=len(deduplicated),
        duration_seconds=round(duration, 2),
    )
    return deduplicated


def _deduplicate_clauses(
    results: list[ClauseExtractionResult],
) -> list[ClauseExtractionResult]:
    """Keep highest-confidence result per (clause_type, chunk_id)."""
    seen: dict[tuple[str, str], ClauseExtractionResult] = {}
    for result in results:
        key = (result.clause_type, result.chunk_id)
        if key not in seen or result.confidence > seen[key].confidence:
            seen[key] = result
    return sorted(seen.values(), key=lambda r: r.clause_type)
