from fastapi import APIRouter, Depends

from app.core.security import verify_api_key
from app.models.schemas import (
    ParseDocumentRequest,
    ParseDocumentResponse,
    ParseOcrRequest,
    ParseStructuredRequest,
    ParseTextResponse,
)
from app.pipeline.router import DocumentPipeline

router = APIRouter(prefix="/parse", tags=["parse"])


@router.post("/ocr", response_model=ParseTextResponse)
async def parse_ocr(
    body: ParseOcrRequest,
    _: str = Depends(verify_api_key),
) -> ParseTextResponse:
    pipeline = DocumentPipeline()
    return pipeline.parse_ocr(
        s3_key=body.s3_key,
        document_url=body.document_url,
        bankruptcy_id=body.bankruptcy_id,
    )


@router.post("/structured", response_model=ParseTextResponse)
async def parse_structured(
    body: ParseStructuredRequest,
    _: str = Depends(verify_api_key),
) -> ParseTextResponse:
    pipeline = DocumentPipeline()
    return pipeline.parse_structured(
        s3_key=body.s3_key,
        document_url=body.document_url,
    )


@router.post("/document", response_model=ParseDocumentResponse)
async def parse_document(
    body: ParseDocumentRequest,
    _: str = Depends(verify_api_key),
) -> ParseDocumentResponse:
    pipeline = DocumentPipeline()
    return pipeline.parse_document(
        bankruptcy_id=body.bankruptcy_id,
        s3_key=body.s3_key,
        document_url=body.document_url,
        docket_hint=body.docket_hint,
        force=body.force,
    )
