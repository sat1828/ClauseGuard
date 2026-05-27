"""
Analysis Router
================
Returns the full FullAnalysisResult for a completed contract analysis.
"""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_session
from models.contract import Contract
from routers.deps import get_current_user_id
from schemas.analysis import FullAnalysisResult

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])


@router.get("/{contract_id}", response_model=FullAnalysisResult)
async def get_analysis(
    contract_id: str,
    db: AsyncSession = Depends(get_session),
    user_id: str = Depends(get_current_user_id),
) -> FullAnalysisResult:
    """
    GET /api/v1/analysis/{contract_id}

    Returns the complete FullAnalysisResult Pydantic model.
    Returns 404 if analysis not yet complete.
    Returns 202 if still processing.
    """
    result = await db.execute(
        select(Contract).where(
            Contract.id == contract_id,
            Contract.user_id == user_id,
        )
    )
    contract = result.scalar_one_or_none()

    if not contract:
        raise HTTPException(status_code=404, detail=f"Contract {contract_id} not found")

    if contract.status == "PROCESSING" or contract.status == "PENDING":
        raise HTTPException(
            status_code=202,
            detail=f"Analysis in progress ({contract.progress_pct}% complete). Poll /status for updates.",
        )

    if contract.status == "FAILED":
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {contract.error_message}",
        )

    if not contract.full_analysis:
        raise HTTPException(
            status_code=404,
            detail="Analysis results not found for this contract",
        )

    return FullAnalysisResult.model_validate(contract.full_analysis)
