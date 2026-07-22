"""
Background job processing without Redis/Celery.

Honest tradeoff (audit note): this queue lives in process memory. If the
server restarts mid-job, that job is lost (the document stays stuck in
"processing"). That's an acceptable tradeoff for a free, zero-infra local
deployment — Celery+Redis would survive a restart but requires running
Redis. If you outgrow this, swap this file for a Celery/ARQ setup; nothing
else in the codebase needs to change since routers only ever call
`enqueue_analysis_job`.
"""
import asyncio
import logging
from datetime import datetime, timezone

from app.config import settings
from app.database import AsyncSessionLocal
from app.models import Document, Clause, DocumentFlag
from app.storage import storage
from app.parsing import parse_document, ParseError
from app.segmentation import segment_clauses
from app.ai_client import analyzer
from app.scoring import compute_overall_score, risk_score_to_label, score_to_label
from app.flags import build_document_flags

logger = logging.getLogger("clauseguard.jobs")

_queue: asyncio.Queue = asyncio.Queue()
_workers: list[asyncio.Task] = []


async def enqueue_analysis_job(document_id: str):
    await _queue.put(document_id)


async def start_workers():
    for i in range(settings.MAX_CONCURRENT_ANALYSES):
        _workers.append(asyncio.create_task(_worker_loop(i)))
    logger.info(f"Started {settings.MAX_CONCURRENT_ANALYSES} analysis workers.")


async def stop_workers():
    for w in _workers:
        w.cancel()
    await asyncio.gather(*_workers, return_exceptions=True)
    _workers.clear()


async def _worker_loop(worker_id: int):
    while True:
        document_id = await _queue.get()
        try:
            await _process_document(document_id)
        except Exception as e:
            logger.exception(f"[worker {worker_id}] Unhandled error processing document {document_id}: {e}")
            await _mark_failed(document_id, "internal_error", str(e))
        finally:
            _queue.task_done()


async def _mark_failed(document_id: str, error_code: str, error_message: str):
    async with AsyncSessionLocal() as db:
        doc = await db.get(Document, document_id)
        if not doc:
            return
        doc.status = "failed"
        doc.error_code = error_code
        doc.error_message = error_message
        doc.processing_completed_at = datetime.now(timezone.utc)
        await db.commit()


async def _process_document(document_id: str):
    async with AsyncSessionLocal() as db:
        doc = await db.get(Document, document_id)
        if not doc:
            logger.warning(f"Document {document_id} not found, skipping.")
            return

        doc.status = "processing"
        doc.processing_started_at = datetime.now(timezone.utc)
        await db.commit()

        # Step 1: fetch file
        try:
            file_bytes = storage.get(doc.storage_key)
        except Exception as e:
            doc.status = "failed"
            doc.error_code = "s3_error"
            doc.error_message = f"Could not read uploaded file: {e}"
            doc.processing_completed_at = datetime.now(timezone.utc)
            await db.commit()
            return

        # Step 2+3: parse (OCR fallback happens inside parse_document)
        try:
            parsed = parse_document(file_bytes, doc.file_type)
        except ParseError as e:
            doc.status = "failed"
            doc.error_code = e.code
            doc.error_message = e.message
            doc.processing_completed_at = datetime.now(timezone.utc)
            await db.commit()
            return

        doc.page_count = parsed.page_count
        doc.word_count = len(parsed.text.split())
        doc.used_ocr = parsed.used_ocr
        await db.commit()

        # Step 4: segment
        clause_texts = segment_clauses(parsed.text)
        if not clause_texts:
            doc.status = "failed"
            doc.error_code = "no_clauses"
            doc.error_message = ("We couldn't identify contract clauses in this document. "
                                  "It may not be a standard legal agreement.")
            doc.processing_completed_at = datetime.now(timezone.utc)
            await db.commit()
            return

        truncated = len(clause_texts) > settings.MAX_CLAUSES_PER_DOCUMENT
        if truncated:
            clause_texts = clause_texts[: settings.MAX_CLAUSES_PER_DOCUMENT]

        doc.clauses_total = len(clause_texts)
        doc.truncated = truncated
        await db.commit()

        # Step 5: analyze each clause (sequential within a document to
        # respect Groq free-tier rate limits; concurrency across DIFFERENT
        # documents is what the worker pool gives you)
        clause_records = []
        failed_count = 0
        for idx, clause_text in enumerate(clause_texts):
            result = await analyzer.analyze_clause(clause_text)

            clause = Clause(document_id=doc.id, clause_index=idx, raw_text=clause_text)
            if result.success:
                data = result.data
                clause.clause_type = data["clause_type"]
                clause.risk_score = data["risk_score"]
                clause.risk_label = risk_score_to_label(data["risk_score"])
                clause.plain_english_explanation = data["plain_english_explanation"]
                clause.suggested_safer_language = data["suggested_safer_language"]
                clause.confidence_score = data["confidence_score"]
                clause.flags = data["flags"]
                clause.analysis_failed = False
            else:
                clause.analysis_failed = True
                clause.failure_reason = result.failure_reason
                failed_count += 1

            db.add(clause)
            await db.commit()
            await db.refresh(clause)

            doc.clauses_processed = idx + 1
            doc.clauses_failed = failed_count
            await db.commit()

            clause_records.append({
                "id": clause.id,
                "risk_score": clause.risk_score,
                "analysis_failed": clause.analysis_failed,
                "flags": clause.flags or [],
            })

        # Step 6: aggregate score
        overall_score = compute_overall_score(clause_records)
        doc.overall_risk_score = overall_score
        doc.overall_risk_label = score_to_label(overall_score)

        # Document-level flags
        for f in build_document_flags(clause_records):
            db.add(DocumentFlag(document_id=doc.id, **f))

        # Step 7/8: finalize
        all_failed = failed_count == len(clause_texts)
        if all_failed:
            doc.status = "failed"
            doc.error_code = "ai_analysis_failed"
            doc.error_message = ("All clauses failed analysis. This is usually a GROQ_API_KEY "
                                  "problem — check your .env file.")
        else:
            doc.status = "complete"
            doc.partial_analysis = failed_count > 0

        doc.processing_completed_at = datetime.now(timezone.utc)
        await db.commit()
