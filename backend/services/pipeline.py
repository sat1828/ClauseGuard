"""
Analysis Pipeline Orchestrator
================================
Coordinates all 7 pipeline stages for a single contract.
Called as a background task after file upload.

Progress updates are written to the Contract DB record so the
frontend's polling endpoint (GET /status) can show real-time progress.

Stage → Progress %:
  0  Classification      →  10%
  1  Parsing             →  20%  (done before this is called, but included for UX)
  2  Chunking            →  30%
  2.5 Embedding          →  45%
  3  Clause Extraction   →  60%
  4  Risk Scoring        →  75%
  5  Alternatives        →  85%
  6  Missing Clauses     →  90%
  7  Finalising          → 100%
"""

import time
import traceback
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import get_session_ctx
from models.contract import ClauseResult, Contract
from schemas.analysis import FullAnalysisResult
from services.alternative_generator import generate_alternatives
from services.chunk_to_clause_map import build_clause_text_map
from services.chunker import chunk_document
from services.classifier import classify_contract
from services.clause_extractor import extract_clauses
from services.document_parser import parse_document
from services.embedder import upsert_chunks
from services.missing_clause_detector import detect_missing_clauses
from services.risk_scorer import compute_overall_risk_score, score_clauses

logger = structlog.get_logger(__name__)
settings = get_settings()


async def _update_status(
    contract_id: str,
    status: str,
    progress_pct: int,
    current_stage: str,
    error_message: str | None = None,
) -> None:
    """Write pipeline progress to DB for the polling endpoint."""
    async with get_session_ctx() as db:
        await db.execute(
            update(Contract)
            .where(Contract.id == contract_id)
            .values(
                status=status,
                progress_pct=progress_pct,
                current_stage=current_stage,
                error_message=error_message,
            )
        )


async def run_analysis_pipeline(contract_id: str, file_path: str, user_id: str) -> None:
    """
    Full 7-stage analysis pipeline.

    This function is invoked as a FastAPI BackgroundTask immediately after
    a successful file upload. It updates the Contract record throughout.

    On any unhandled exception: marks the contract as FAILED and logs the
    full traceback to structlog. Does NOT reraise (background task).
    """
    pipeline_start = time.time()
    logger.info("pipeline_started", contract_id=contract_id, user_id=user_id)

    try:
        # ── Stage 1: Document Parsing (already partially done at upload) ──────
        await _update_status(contract_id, "PROCESSING", 10, "Parsing document...")
        parsed_doc = parse_document(file_path)
        logger.info(
            "stage1_complete",
            contract_id=contract_id,
            pages=parsed_doc.total_pages,
            blocks=len(parsed_doc.blocks),
        )

        # ── Stage 0: Contract Classification ─────────────────────────────────
        await _update_status(contract_id, "PROCESSING", 20, "Identifying contract type...")
        contract_type_result = await classify_contract(parsed_doc.raw_text, contract_id)
        contract_type = contract_type_result.contract_type
        jurisdiction = contract_type_result.jurisdiction_hint or "Unknown"
        logger.info("stage0_complete", contract_id=contract_id, type=contract_type)

        # ── Stage 2: Legal-Aware Chunking ─────────────────────────────────────
        await _update_status(contract_id, "PROCESSING", 30, "Chunking document...")
        chunks = chunk_document(parsed_doc, contract_type)
        logger.info("stage2_complete", contract_id=contract_id, chunks=len(chunks))

        # ── Stage 2.5: Embedding + Pinecone Upsert ────────────────────────────
        await _update_status(contract_id, "PROCESSING", 45, "Indexing for search...")
        pinecone_namespace = await upsert_chunks(chunks, contract_id)

        # ── Stage 3: Clause Extraction ────────────────────────────────────────
        await _update_status(contract_id, "PROCESSING", 60, "Extracting clauses...")
        extracted_clauses = await extract_clauses(chunks, contract_type, jurisdiction, contract_id)
        logger.info(
            "stage3_complete",
            contract_id=contract_id,
            clauses=len(extracted_clauses),
        )

        # ── Stage 4: Risk Scoring ─────────────────────────────────────────────
        await _update_status(contract_id, "PROCESSING", 75, "Scoring risks...")
        risk_assessments = await score_clauses(
            extracted_clauses, contract_type, jurisdiction, contract_id
        )
        overall_score = compute_overall_risk_score(risk_assessments)
        logger.info(
            "stage4_complete",
            contract_id=contract_id,
            assessments=len(risk_assessments),
            overall_score=overall_score,
        )

        # ── Stage 5: Alternative Clause Generation ────────────────────────────
        await _update_status(contract_id, "PROCESSING", 85, "Generating alternatives...")
        clause_text_map = build_clause_text_map(extracted_clauses)
        alternatives = await generate_alternatives(
            risk_assessments, clause_text_map, contract_type, jurisdiction, contract_id
        )
        logger.info("stage5_complete", contract_id=contract_id, alternatives=len(alternatives))

        # ── Stage 6: Missing Clause Detection ────────────────────────────────
        await _update_status(contract_id, "PROCESSING", 90, "Checking for missing clauses...")
        missing_clauses = detect_missing_clauses(extracted_clauses, contract_type, contract_id)
        logger.info(
            "stage6_complete",
            contract_id=contract_id,
            missing=len(missing_clauses),
        )

        # ── Finalise: Assemble FullAnalysisResult ────────────────────────────
        await _update_status(contract_id, "PROCESSING", 95, "Finalising analysis...")

        duration = time.time() - pipeline_start
        analyzed_at = datetime.now(timezone.utc)

        critical_count = sum(1 for r in risk_assessments if r.risk_level == "CRITICAL")
        high_count = sum(1 for r in risk_assessments if r.risk_level == "HIGH")
        medium_count = sum(1 for r in risk_assessments if r.risk_level == "MEDIUM")
        low_count = sum(1 for r in risk_assessments if r.risk_level == "LOW")

        full_result = FullAnalysisResult(
            contract_id=contract_id,
            contract_type=contract_type_result,
            extracted_clauses=extracted_clauses,
            risk_assessments=risk_assessments,
            alternatives=alternatives,
            missing_clauses=missing_clauses,
            overall_risk_score=overall_score,
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            total_clauses_found=len(extracted_clauses),
            analysis_duration_seconds=round(duration, 2),
            pipeline_version=settings.PIPELINE_VERSION,
            analyzed_at=analyzed_at,
        )

        # ── Persist results ───────────────────────────────────────────────────
        async with get_session_ctx() as db:
            # Save individual ClauseResult rows for analytics
            for assessment in risk_assessments:
                # Find matching extraction for page range
                matching = next(
                    (e for e in extracted_clauses if e.clause_type == assessment.clause_type),
                    None,
                )
                clause_row = ClauseResult(
                    id=str(uuid.uuid4()),
                    contract_id=contract_id,
                    clause_type=assessment.clause_type,
                    risk_level=assessment.risk_level,
                    risk_score=assessment.risk_score,
                    relevant_text=assessment.source_text[:2000] if assessment.source_text else None,
                    plain_english_summary=assessment.plain_english_summary,
                    why_it_matters=assessment.why_it_matters,
                    chunk_id=matching.chunk_id if matching else None,
                )
                db.add(clause_row)

            # Update Contract record with full results
            await db.execute(
                update(Contract)
                .where(Contract.id == contract_id)
                .values(
                    status="COMPLETE",
                    progress_pct=100,
                    current_stage="Analysis complete",
                    contract_type=contract_type,
                    overall_risk_score=overall_score,
                    critical_count=critical_count,
                    high_count=high_count,
                    medium_count=medium_count,
                    low_count=low_count,
                    full_analysis=full_result.model_dump(mode="json"),
                    pinecone_namespace=pinecone_namespace,
                    analysis_duration_seconds=round(duration, 2),
                    analyzed_at=analyzed_at,
                )
            )

        logger.info(
            "pipeline_complete",
            contract_id=contract_id,
            duration_seconds=round(duration, 2),
            overall_score=overall_score,
            clauses_found=len(extracted_clauses),
            alternatives_generated=len(alternatives),
            missing_clauses=len(missing_clauses),
        )

    except Exception as exc:
        duration = time.time() - pipeline_start
        error_msg = f"{type(exc).__name__}: {str(exc)}"
        full_trace = traceback.format_exc()

        logger.error(
            "pipeline_failed",
            contract_id=contract_id,
            error=error_msg,
            duration_seconds=round(duration, 2),
            traceback=full_trace,
        )

        await _update_status(
            contract_id,
            "FAILED",
            0,
            "Analysis failed",
            error_message=error_msg[:500],
        )
