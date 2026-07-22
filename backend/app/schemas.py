from pydantic import BaseModel, EmailStr, Field, ConfigDict


# ---- Auth ----
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class VerifyEmailRequest(BaseModel):
    token: str


class RequestPasswordResetRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: str
    email: str
    plan: str
    analyses_used: int
    analyses_limit: int
    email_verified: bool

    model_config = ConfigDict(from_attributes=True)


# ---- Documents ----
class DocumentUploadResponse(BaseModel):
    document_id: str
    status: str


class DocumentStatusResponse(BaseModel):
    id: str
    status: str
    clauses_total: int
    clauses_processed: int
    clauses_failed: int
    error_code: str | None = None
    error_message: str | None = None


class ClauseResult(BaseModel):
    id: str
    clause_index: int
    raw_text: str
    clause_type: str | None
    clause_type_label: str
    risk_score: int | None
    risk_label: str | None
    plain_english_explanation: str | None
    suggested_safer_language: str | None
    confidence_score: float | None
    low_confidence: bool
    analysis_failed: bool
    failure_reason: str | None
    flags: list[str]


class FlagResult(BaseModel):
    id: str
    flag_type: str
    severity: str
    summary: str
    affected_clause_id: str | None


DISCLAIMER = (
    "ClauseGuard provides information, not legal advice. AI analysis may contain errors. "
    "For contracts with significant financial or legal exposure, consult a licensed attorney before signing."
)


class DocumentResults(BaseModel):
    id: str
    filename: str
    status: str
    overall_risk_score: float | None
    overall_risk_label: str | None
    page_count: int | None
    word_count: int | None
    used_ocr: bool
    partial_analysis: bool
    truncated: bool
    clauses_total: int
    clauses_processed: int
    clauses_failed: int
    flags: list[FlagResult]
    clauses: list[ClauseResult]
    disclaimer: str = DISCLAIMER


class ErrorDetail(BaseModel):
    code: str
    message: str
    action: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
