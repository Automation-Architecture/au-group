from fastapi import APIRouter, Depends, Request

from app.core.config import get_settings
from app.core.security import verify_auth
from app.core.rate_limit import limiter
from app.models.schemas import (
    ExtractCreditorMatrixRequest,
    ExtractCreditorMatrixResponse,
    ExtractForm201Request,
    ExtractForm201Response,
)
from app.pipeline.router import DocumentPipeline

router = APIRouter(prefix="/extract", tags=["extract"])

_extract_rate_limit = lambda: get_settings().rate_limit_extract  # noqa: E731


@router.post("/form201", response_model=ExtractForm201Response)
@limiter.limit(_extract_rate_limit)
async def extract_form201(
    request: Request,
    body: ExtractForm201Request,
    _auth=Depends(verify_auth),
) -> ExtractForm201Response:
    pipeline = DocumentPipeline()
    return pipeline.extract_form201(
        bankruptcy_id=body.bankruptcy_id,
        s3_key=body.s3_key,
        docket_hint=body.docket_hint,
        force=body.force,
    )


@router.post("/creditor-matrix", response_model=ExtractCreditorMatrixResponse)
@limiter.limit(_extract_rate_limit)
async def extract_creditor_matrix(
    request: Request,
    body: ExtractCreditorMatrixRequest,
    _auth=Depends(verify_auth),
) -> ExtractCreditorMatrixResponse:
    pipeline = DocumentPipeline()
    return pipeline.extract_creditor_matrix(
        bankruptcy_id=body.bankruptcy_id,
        s3_key=body.s3_key,
        docket_hint=body.docket_hint,
        force=body.force,
    )
