from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.exceptions import BackgroundJobBusyError, DocumentProcessingError
from app.core.rate_limit import limiter
from app.core.security import verify_auth
from app.models.schemas import (
    ExtractCreditorMatrixRequest,
    ExtractCreditorMatrixResponse,
    ExtractForm201Request,
    ExtractForm201Response,
)
from app.pipeline.router import DocumentPipeline

router = APIRouter(prefix="/extract", tags=["extract"])

_extract_rate_limit = lambda: get_settings().rate_limit_extract  # noqa: E731


@router.post(
    "/form201",
    response_model=ExtractForm201Response,
    summary="Extract Form 201",
    description="Use to get Form 201 debtor and estate fields from an uploaded document.",
    responses={
        409: {"description": "Document still processing; poll job status first"},
        429: {"description": "Too many concurrent background jobs"},
    },
)
@limiter.limit(_extract_rate_limit)
async def extract_form201(
    request: Request,
    body: ExtractForm201Request,
    _auth=Depends(verify_auth),
) -> ExtractForm201Response | JSONResponse:
    pipeline = DocumentPipeline()
    try:
        return pipeline.extract_form201(
            bankruptcy_id=body.bankruptcy_id,
            s3_key=body.s3_key,
            docket_hint=body.docket_hint,
            force=body.force,
        )
    except DocumentProcessingError as exc:
        return JSONResponse(status_code=409, content={"detail": str(exc)})
    except BackgroundJobBusyError as exc:
        return JSONResponse(status_code=429, content={"detail": str(exc)})


@router.post(
    "/creditor-matrix",
    response_model=ExtractCreditorMatrixResponse,
    summary="Extract creditor matrix",
    description="Use to get the creditor list from an uploaded creditor matrix document.",
    responses={
        409: {"description": "Document still processing; poll job status first"},
        429: {"description": "Too many concurrent background jobs"},
    },
)
@limiter.limit(_extract_rate_limit)
async def extract_creditor_matrix(
    request: Request,
    body: ExtractCreditorMatrixRequest,
    _auth=Depends(verify_auth),
) -> ExtractCreditorMatrixResponse | JSONResponse:
    pipeline = DocumentPipeline()
    try:
        return pipeline.extract_creditor_matrix(
            bankruptcy_id=body.bankruptcy_id,
            s3_key=body.s3_key,
            docket_hint=body.docket_hint,
            force=body.force,
        )
    except DocumentProcessingError as exc:
        return JSONResponse(status_code=409, content={"detail": str(exc)})
    except BackgroundJobBusyError as exc:
        return JSONResponse(status_code=429, content={"detail": str(exc)})
