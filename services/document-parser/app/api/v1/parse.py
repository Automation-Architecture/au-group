from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.exceptions import (
    BackgroundJobBusyError,
    BankruptcyIdRequiredError,
    DocumentProcessingError,
)
from app.core.rate_limit import limiter
from app.core.security import verify_auth
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


def _parse_document_response(result: ParseDocumentResponse) -> ParseDocumentResponse | JSONResponse:
    if result.status == "processing":
        return JSONResponse(status_code=202, content=result.model_dump(mode="json"))
    if result.status == "failed":
        return JSONResponse(status_code=500, content=result.model_dump(mode="json"))
    return result


@router.post(
    "/ocr",
    response_model=ParseTextResponse,
    summary="OCR parse",
    description="Use to read text from a scanned or image-based PDF.",
)
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


@router.post(
    "/structured",
    response_model=ParseTextResponse,
    summary="Structured parse",
    description="Use to read text from a PDF that already has selectable text (no OCR).",
)
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


@router.post(
    "/document",
    response_model=ParseDocumentResponse,
    summary="Parse document",
    description=(
        "Use to parse a bankruptcy filing end-to-end: classify type, extract fields, validate, and save. "
        "n8n calls this after a PDF is uploaded. Set async_mode to parse in the background and poll /jobs/{id}."
    ),
    responses={
        202: {"model": ParseDocumentResponse, "description": "Parse accepted; poll job status"},
        409: {"description": "Document still processing"},
        429: {"description": "Too many concurrent background jobs"},
        500: {"model": ParseDocumentResponse, "description": "Background parse failed"},
    },
)
@limiter.limit(_parse_rate_limit)
async def parse_document(
    request: Request,
    body: ParseDocumentRequest,
    background_tasks: BackgroundTasks,
    _auth=Depends(verify_auth),
) -> ParseDocumentResponse | JSONResponse:
    settings = get_settings()
    if settings.require_bankruptcy_id and body.bankruptcy_id is None:
        raise BankruptcyIdRequiredError()

    pipeline = DocumentPipeline()
    try:
        result, schedule_background, temp_path, content_hash, _resolved_key, release_slot = (
            pipeline.parse_document(
            bankruptcy_id=body.bankruptcy_id,
            s3_key=body.s3_key,
            document_url=body.document_url,
            docket_hint=body.docket_hint,
            force=body.force,
            async_mode=body.async_mode,
            )
        )
    except DocumentProcessingError as exc:
        return JSONResponse(status_code=409, content={"detail": str(exc)})
    except BackgroundJobBusyError as exc:
        return JSONResponse(status_code=429, content={"detail": str(exc)})

    if schedule_background and result.document_id is not None:
        correlation_id = getattr(request.state, "request_id", None)
        background_tasks.add_task(
            pipeline.run_parse_document_background,
            document_id=result.document_id,
            bankruptcy_id=body.bankruptcy_id,
            s3_key=body.s3_key,
            document_url=body.document_url,
            docket_hint=body.docket_hint,
            temp_path=temp_path,
            content_hash=content_hash,
            release_slot=release_slot,
            correlation_id=correlation_id,
        )
    return _parse_document_response(result)
