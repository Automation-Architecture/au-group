from fastapi import APIRouter, Depends

from app.core.security import verify_api_key
from app.models.schemas import (
    ExtractCreditorMatrixRequest,
    ExtractCreditorMatrixResponse,
    ExtractForm201Request,
    ExtractForm201Response,
)
from app.pipeline.router import DocumentPipeline

router = APIRouter(prefix="/extract", tags=["extract"])


@router.post("/form201", response_model=ExtractForm201Response)
async def extract_form201(
    body: ExtractForm201Request,
    _: str = Depends(verify_api_key),
) -> ExtractForm201Response:
    pipeline = DocumentPipeline()
    return pipeline.extract_form201(
        bankruptcy_id=body.bankruptcy_id,
        s3_key=body.s3_key,
        docket_hint=body.docket_hint,
        force=body.force,
    )


@router.post("/creditor-matrix", response_model=ExtractCreditorMatrixResponse)
async def extract_creditor_matrix(
    body: ExtractCreditorMatrixRequest,
    _: str = Depends(verify_api_key),
) -> ExtractCreditorMatrixResponse:
    pipeline = DocumentPipeline()
    return pipeline.extract_creditor_matrix(
        bankruptcy_id=body.bankruptcy_id,
        s3_key=body.s3_key,
        docket_hint=body.docket_hint,
        force=body.force,
    )
