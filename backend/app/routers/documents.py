from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import User, Document, Clause, DocumentFlag
from app.deps import get_current_user
from app.validation import validate_and_read_upload
from app.storage import storage
from app.utils import build_storage_key
from app.job_queue import enqueue_analysis_job
from app.taxonomy import human_label
from app.schemas import (
    DocumentUploadResponse, DocumentStatusResponse, DocumentResults,
    ClauseResult, FlagResult,
)

router = APIRouter(prefix="/api/documents", tags=["documents"])

LOW_CONFIDENCE_THRESHOLD = 0.6


async def _get_owned_document(document_id: str, user: User, db: AsyncSession) -> Document:
    doc = await db.get(Document, document_id)
    if not doc or doc.user_id != user.id:
        # Same 404 whether it doesn't exist or belongs to someone else —
        # never leak which one it is.
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return doc


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.analyses_used >= current_user.analyses_limit:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Analysis limit reached. Please upgrade your plan.",
        )

    file_bytes, file_type = await validate_and_read_upload(file)

    document = Document(
        user_id=current_user.id,
        filename=file.filename or "upload",
        storage_key="",  # set after we have the document id
        file_type=file_type,
        status="pending",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    storage_key = build_storage_key(current_user.id, document.id, file.filename or "upload")
    storage.put(storage_key, file_bytes)
    document.storage_key = storage_key

    current_user.analyses_used += 1
    await db.commit()

    await enqueue_analysis_job(document.id)

    return DocumentUploadResponse(document_id=document.id, status="pending")


@router.get("/", response_model=list[DocumentStatusResponse])
async def list_documents(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.scalars(
        select(Document).where(Document.user_id == current_user.id).order_by(Document.created_at.desc())
    )
    docs = result.all()
    return [
        DocumentStatusResponse(
            id=d.id, status=d.status, clauses_total=d.clauses_total,
            clauses_processed=d.clauses_processed, clauses_failed=d.clauses_failed,
            error_code=d.error_code, error_message=d.error_message,
        ) for d in docs
    ]


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_status(document_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    doc = await _get_owned_document(document_id, current_user, db)
    return DocumentStatusResponse(
        id=doc.id, status=doc.status, clauses_total=doc.clauses_total,
        clauses_processed=doc.clauses_processed, clauses_failed=doc.clauses_failed,
        error_code=doc.error_code, error_message=doc.error_message,
    )


@router.get("/{document_id}/results", response_model=DocumentResults)
async def get_results(document_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    doc = await _get_owned_document(document_id, current_user, db)

    clauses_result = await db.scalars(
        select(Clause).where(Clause.document_id == doc.id).order_by(Clause.clause_index)
    )
    flags_result = await db.scalars(select(DocumentFlag).where(DocumentFlag.document_id == doc.id))

    clause_out = [
        ClauseResult(
            id=c.id,
            clause_index=c.clause_index,
            raw_text=c.raw_text,
            clause_type=c.clause_type,
            clause_type_label=human_label(c.clause_type),
            risk_score=c.risk_score,
            risk_label=c.risk_label,
            plain_english_explanation=c.plain_english_explanation,
            suggested_safer_language=c.suggested_safer_language,
            confidence_score=float(c.confidence_score) if c.confidence_score is not None else None,
            low_confidence=(c.confidence_score is not None and float(c.confidence_score) < LOW_CONFIDENCE_THRESHOLD),
            analysis_failed=c.analysis_failed,
            failure_reason=c.failure_reason,
            flags=c.flags or [],
        )
        for c in clauses_result.all()
    ]

    flag_out = [
        FlagResult(id=f.id, flag_type=f.flag_type, severity=f.severity,
                    summary=f.summary, affected_clause_id=f.affected_clause_id)
        for f in flags_result.all()
    ]

    return DocumentResults(
        id=doc.id,
        filename=doc.filename,
        status=doc.status,
        overall_risk_score=float(doc.overall_risk_score) if doc.overall_risk_score is not None else None,
        overall_risk_label=doc.overall_risk_label,
        page_count=doc.page_count,
        word_count=doc.word_count,
        used_ocr=doc.used_ocr,
        partial_analysis=doc.partial_analysis,
        truncated=doc.truncated,
        clauses_total=doc.clauses_total,
        clauses_processed=doc.clauses_processed,
        clauses_failed=doc.clauses_failed,
        flags=flag_out,
        clauses=clause_out,
    )


@router.get("/{document_id}/clauses", response_model=list[ClauseResult])
async def get_clauses(document_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    doc = await _get_owned_document(document_id, current_user, db)
    clauses_result = await db.scalars(
        select(Clause).where(Clause.document_id == doc.id).order_by(Clause.clause_index)
    )
    return [
        ClauseResult(
            id=c.id, clause_index=c.clause_index, raw_text=c.raw_text,
            clause_type=c.clause_type, clause_type_label=human_label(c.clause_type),
            risk_score=c.risk_score, risk_label=c.risk_label,
            plain_english_explanation=c.plain_english_explanation,
            suggested_safer_language=c.suggested_safer_language,
            confidence_score=float(c.confidence_score) if c.confidence_score is not None else None,
            low_confidence=(c.confidence_score is not None and float(c.confidence_score) < LOW_CONFIDENCE_THRESHOLD),
            analysis_failed=c.analysis_failed, failure_reason=c.failure_reason, flags=c.flags or [],
        )
        for c in clauses_result.all()
    ]


@router.get("/{document_id}/flags", response_model=list[FlagResult])
async def get_flags(document_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    doc = await _get_owned_document(document_id, current_user, db)
    flags_result = await db.scalars(select(DocumentFlag).where(DocumentFlag.document_id == doc.id))
    return [
        FlagResult(id=f.id, flag_type=f.flag_type, severity=f.severity,
                    summary=f.summary, affected_clause_id=f.affected_clause_id)
        for f in flags_result.all()
    ]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: str, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    doc = await _get_owned_document(document_id, current_user, db)
    try:
        storage.delete(doc.storage_key)
    except Exception:
        pass  # file already gone / never written — don't block the DB delete
    await db.delete(doc)
    await db.commit()
