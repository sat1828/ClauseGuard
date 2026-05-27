"""
Contract HTTP Request/Response Schemas
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ContractUploadResponse(BaseModel):
    contract_id: str
    filename: str
    status: str = "processing"
    message: str = "Contract received. Analysis pipeline started."


class ContractStatusResponse(BaseModel):
    contract_id: str
    status: str  # PENDING | PROCESSING | COMPLETE | FAILED
    progress_pct: int = Field(ge=0, le=100)
    current_stage: Optional[str] = None
    error_message: Optional[str] = None


class ContractListItem(BaseModel):
    contract_id: str
    filename: str
    analyzed_at: Optional[datetime]
    overall_risk_score: Optional[float]
    contract_type: Optional[str]
    status: str
    critical_count: Optional[int] = 0
    high_count: Optional[int] = 0
