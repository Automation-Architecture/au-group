from fastapi import APIRouter, Depends, Request

from app.core.config import get_settings
from app.core.security import verify_auth
from app.core.rate_limit import limiter
from app.models.schemas import (
    ParseDocumentRequest,
    ParseDocumentResponse,
    ParseOcrRequest,
    ParseStructuredRequest,
    ParseTextResponse,
)
from app.pipeline.router import DocumentPipeline

router = APIRouter(prefix="/parse", tags=["parse"])

_parse_rate_limit = lambda: get_settings().rate_limit_parse  # noqa: E731


@router.post("/ocr", response_model=ParseTextResponse)
@limiter.limit(_parse_rate_limit)
async def parse_ocr(
    request: Request,
    body: ParseOcrRequest,
    _auth=Depends(verify_auth),
) -> ParseTextResponse:
    pipeline = DocumentPipeline()
    return pipeline.parse_ocr(
        s3_key=body.s3_key,
        document_url=body.document_url,
        bankruptcy_id=body.bankruptcy_id,
    )


@router.post("/structured", response_model=ParseTextResponse)
@limiter.limit(_parse_rate_limit)
async def parse_structured(
    request: Request,
    body: ParseStructuredRequest,
    _auth=Depends(verify_auth),
) -> ParseTextResponse:
    pipeline = DocumentPipeline()
    return pipeline.parse_structured(
        s3_key=body.s3_key,
        document_url=body.document_url,
    )


@router.post("/document", response_model=ParseDocumentResponse)
@limiter.limit(_parse_rate_limit)
async def parse_document(
    request: Request,
    body: ParseDocumentRequest,
    _auth=Depends(verify_auth),
) -> ParseDocumentResponse:
    pipeline = DocumentPipeline()
    return pipeline.parse_document(
        bankruptcy_id=body.bankruptcy_id,
        s3_key=body.s3_key,
        document_url=body.document_url,
        docket_hint=body.docket_hint,
        force=body.force,
    )
