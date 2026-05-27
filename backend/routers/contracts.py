"""
Contracts Router
=================
Handles file upload, contract listing, status polling, and deletion.

Upload is async: file is saved, a DB record created, and the pipeline
is launched as a BackgroundTask. The upload endpoint returns immediately.
Frontend polls GET /status every 2 seconds.
"""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import get_session
from models.contract import Contract
from schemas.contract import (
    ContractListItem,
    ContractStatusResponse,
    ContractUploadResponse,
)
from services.pipeline import run_analysis_pipeline
from routers.deps import get_current_user_id

logger = structlog.get_logger(__name__)
settings = get_settings()

router = APIRouter(prefix="/api/v1/contracts", tags=["contracts"])





@router.post("/upload", response_model=ContractUploadResponse, status_code=202)
async def upload_contract(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
) -> ContractUploadResponse:
    """
    POST /api/v1/contracts/upload

    Accepts multipart/form-data with a PDF, DOCX, or TXT file.
    Returns immediately with contract_id. Client polls /status for progress.
    """
    # ── Validation ────────────────────────────────────────────────────────────
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in settings.supported_extensions:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type '{file_ext}'. Supported: {settings.SUPPORTED_FILE_TYPES}",
        )

    # Read file content and check size before saving
    content = await file.read()
    if len(content) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE_MB}MB",
        )

    # ── Save file ─────────────────────────────────────────────────────────────
    contract_id = str(uuid.uuid4())
    safe_filename = f"{contract_id}{file_ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, safe_filename)

    with open(file_path, "wb") as f:
        f.write(content)

    logger.info(
        "contract_uploaded",
        contract_id=contract_id,
        filename=file.filename,
        size_bytes=len(content),
        user_id=user_id,
    )

    # ── Create DB record ──────────────────────────────────────────────────────
    contract = Contract(
        id=contract_id,
        user_id=user_id,
        filename=file.filename,
        file_path=file_path,
        file_size_bytes=len(content),
        mime_type=file.content_type or "application/octet-stream",
        status="PENDING",
        progress_pct=0,
        current_stage="Queued for analysis",
        created_at=datetime.now(timezone.utc),
    )
    db.add(contract)
    # Session commits automatically via get_session dependency

    # ── Kick off pipeline as background task ──────────────────────────────────
    # BackgroundTask runs after the response is sent — non-blocking upload UX.
    background_tasks.add_task(run_analysis_pipeline, contract_id, file_path, user_id)

    return ContractUploadResponse(
        contract_id=contract_id,
        filename=file.filename,
        status="processing",
    )


@router.get("/", response_model=list[ContractListItem])
async def list_contracts(
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
) -> list[ContractListItem]:
    """
    GET /api/v1/contracts/

    Returns all contracts for the current user, newest first.
    Used for the dashboard contract history list.
    """
    result = await db.execute(
        select(Contract)
        .where(Contract.user_id == user_id)
        .order_by(Contract.created_at.desc())
        .limit(50)
    )
    contracts = result.scalars().all()

    return [
        ContractListItem(
            contract_id=c.id,
            filename=c.filename,
            analyzed_at=c.analyzed_at,
            overall_risk_score=c.overall_risk_score,
            contract_type=c.contract_type,
            status=c.status,
            critical_count=c.critical_count or 0,
            high_count=c.high_count or 0,
        )
        for c in contracts
    ]


@router.get("/{contract_id}/status", response_model=ContractStatusResponse)
async def get_contract_status(
    contract_id: str,
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
) -> ContractStatusResponse:
    """
    GET /api/v1/contracts/{contract_id}/status

    Polled by frontend every 2 seconds during analysis.
    Returns pipeline progress and current stage description.
    """
    contract = await _get_contract_or_404(db, contract_id, user_id)

    return ContractStatusResponse(
        contract_id=contract.id,
        status=contract.status,
        progress_pct=contract.progress_pct,
        current_stage=contract.current_stage,
        error_message=contract.error_message,
    )


@router.delete("/{contract_id}", status_code=204)
async def delete_contract(
    contract_id: str,
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
) -> None:
    """
    DELETE /api/v1/contracts/{contract_id}

    Deletes: DB record (CASCADE deletes clauses + chat messages),
             uploaded file from disk,
             Pinecone namespace for this contract.
    """
    contract = await _get_contract_or_404(db, contract_id, user_id)

    # Delete Pinecone namespace
    if contract.pinecone_namespace:
        from services.embedder import delete_contract_namespace
        await delete_contract_namespace(contract_id)

    # Delete file from disk
    if contract.file_path and os.path.exists(contract.file_path):
        try:
            os.remove(contract.file_path)
        except OSError as e:
            logger.warning("file_deletion_failed", path=contract.file_path, error=str(e))

    # Delete DB record (CASCADE handles related rows)
    await db.delete(contract)

    logger.info("contract_deleted", contract_id=contract_id, user_id=user_id)


async def _get_contract_or_404(
    db: AsyncSession,
    contract_id: str,
    user_id: str,
) -> Contract:
    """Fetch a contract by ID, enforcing user ownership."""
    result = await db.execute(
        select(Contract).where(
            Contract.id == contract_id,
            Contract.user_id == user_id,
        )
    )
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(
            status_code=404,
            detail=f"Contract {contract_id} not found",
        )
    return contract
