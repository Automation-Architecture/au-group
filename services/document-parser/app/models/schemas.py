from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.s3_validation import validate_s3_key


class FilingType(str, Enum):
    FORM_201 = "FORM_201"
    CREDITOR_MATRIX = "CREDITOR_MATRIX"
    SCHEDULE = "SCHEDULE"
    SOFA = "SOFA"
    UNKNOWN = "UNKNOWN"


class ParseMode(str, Enum):
    STRUCTURED = "structured"
    OCR = "ocr"


class UsdRange(BaseModel):
    min_usd: float | None = None
    max_usd: float | None = None


class CountRange(BaseModel):
    min: int | None = None
    max: int | None = None


class Form201Data(BaseModel):
    debtor_name: str | None = None
    city: str | None = None
    state: str | None = None
    court_district: str | None = None
    industry_code: str | None = None
    estimated_assets: UsdRange | None = None
    estimated_liabilities: UsdRange | None = None
    estimated_creditor_count: CountRange | None = None


class CreditorRow(BaseModel):
    creditor_name: str
    address: str | None = None
    claim_amount: float | None = None
    entity_type: str | None = None
    original_name: str | None = None
    confidence_score: float | None = None


class ValidationResult(BaseModel):
    confidence_score: float
    manual_review_required: bool
    missing_fields: list[str] = Field(default_factory=list)
    level: str = "high"


class DocumentSource(BaseModel):
    document_url: str | None = None
    s3_key: str | None = None
    bankruptcy_id: UUID | None = None
    docket_hint: FilingType | None = None
    force: bool = False

    @field_validator("s3_key")
    @classmethod
    def validate_source_s3_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_s3_key(value, operation="read")


class ParseOcrRequest(DocumentSource):
    pass


class ParseStructuredRequest(DocumentSource):
    pass


class ParseDocumentRequest(DocumentSource):
    async_mode: bool = False


class ExtractForm201Request(BaseModel):
    bankruptcy_id: UUID
    s3_key: str
    docket_hint: FilingType | None = None
    force: bool = False

    @field_validator("s3_key")
    @classmethod
    def validate_extract_s3_key(cls, value: str) -> str:
        return validate_s3_key(value, operation="read")


class ExtractCreditorMatrixRequest(BaseModel):
    bankruptcy_id: UUID
    s3_key: str
    docket_hint: FilingType | None = None
    force: bool = False

    @field_validator("s3_key")
    @classmethod
    def validate_matrix_s3_key(cls, value: str) -> str:
        return validate_s3_key(value, operation="read")


class ParseTextResponse(BaseModel):
    text: str
    page_count: int
    ocr_used: bool
    confidence: float | None = None
    parse_mode: ParseMode
    document_id: UUID | None = None


class ExtractForm201Response(BaseModel):
    filing_type: FilingType
    form201: Form201Data
    validation: ValidationResult
    document_id: UUID | None = None


class ExtractCreditorMatrixResponse(BaseModel):
    filing_type: FilingType
    creditors: list[CreditorRow]
    validation: ValidationResult
    document_id: UUID | None = None
    creditor_count: int = 0


class ParseDocumentResponse(BaseModel):
    status: str = "completed"
    filing_type: FilingType = FilingType.UNKNOWN
    parse_mode: ParseMode = ParseMode.STRUCTURED
    ocr_used: bool = False
    page_count: int = 0
    confidence: float = 0.0
    manual_review_required: bool = False
    document_id: UUID | None = None
    form201: Form201Data | None = None
    creditors: list[CreditorRow] | None = None
    validation: ValidationResult | None = None
    error: str | None = None


class ReviewQueueItem(BaseModel):
    id: UUID
    bankruptcy_id: UUID | None
    document_id: UUID | None
    review_reason: str
    status: str
    assigned_to: str | None
    created_at: str


class ReviewQueueResponse(BaseModel):
    items: list[ReviewQueueItem]
    total: int
    limit: int
    offset: int


class JobStatusResponse(BaseModel):
    document_id: UUID
    status: str
    parser_version: str
    filing_type: FilingType | None
    manual_review_required: bool
    result: dict[str, Any] | None = None
    error: str | None = None


class ResolveReviewRequest(BaseModel):
    resolved_by: str | None = None


class ResolveReviewResponse(BaseModel):
    review_id: UUID
    document_id: UUID | None
    bankruptcy_id: UUID | None
    status: str
    bankruptcy_manual_review_required: bool | None = None


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
