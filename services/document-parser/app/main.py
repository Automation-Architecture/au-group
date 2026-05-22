import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import (
    BackgroundJobBusyError,
    BankruptcyIdRequiredError,
    BankruptcyNotFoundError,
    DocumentProcessingError,
)
from app.core.logging import configure_logging, log_event
from app.core.rate_limit import limiter
from app.core.readiness import run_readiness_checks
from app.core.request_context import bind_request_id, new_request_id, reset_request_id
from app.persistence.supabase import SupabaseUnavailableError

configure_logging()
logger = logging.getLogger(__name__)

_settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    logger.info("document_parser_starting", extra={"parser_version": settings.parser_version})
    yield
    logger.info("document_parser_stopped")


_OPENAPI_TAGS = [
    {"name": "health", "description": "Service health checks."},
    {"name": "auth", "description": "Get an access token for API calls."},
    {"name": "parse", "description": "Read text from uploaded PDFs."},
    {"name": "extract", "description": "Pull structured data from parsed filings."},
    {"name": "review", "description": "Track parse jobs and manual review items."},
]

app = FastAPI(
    title="AU Group Document Parser",
    description="SYS-02A OCR and bankruptcy document parsing service",
    version=_settings.parser_version,
    lifespan=lifespan,
    docs_url="/docs" if _settings.expose_openapi else None,
    redoc_url=None,
    openapi_url="/openapi.json" if _settings.expose_openapi else None,
    openapi_tags=_OPENAPI_TAGS,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    correlation_id = (
        request.headers.get("X-Request-ID")
        or request.headers.get("X-Correlation-ID")
        or new_request_id()
    )
    request.state.request_id = correlation_id
    token = bind_request_id(correlation_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = correlation_id
        return response
    finally:
        reset_request_id(token)


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    if request.url.path.startswith("/api/"):
        log_event(
            logger,
            "http_request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(elapsed_ms, 2),
            correlation_id=getattr(request.state, "request_id", None),
        )
    return response


@app.exception_handler(BankruptcyIdRequiredError)
async def bankruptcy_id_required_handler(
    request: Request, exc: BankruptcyIdRequiredError
) -> JSONResponse:
    logger.warning("bad_request path=%s", request.url.path, exc_info=exc)
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(BankruptcyNotFoundError)
async def bankruptcy_not_found_handler(
    request: Request, exc: BankruptcyNotFoundError
) -> JSONResponse:
    logger.warning("bankruptcy_not_found path=%s", request.url.path, exc_info=exc)
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(DocumentProcessingError)
async def document_processing_handler(
    request: Request, exc: DocumentProcessingError
) -> JSONResponse:
    logger.warning("conflict path=%s", request.url.path, exc_info=exc)
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(BackgroundJobBusyError)
async def background_busy_handler(request: Request, exc: BackgroundJobBusyError) -> JSONResponse:
    logger.warning("rate_limited path=%s", request.url.path, exc_info=exc)
    return JSONResponse(status_code=429, content={"detail": str(exc)})


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    logger.warning("bad_request path=%s", request.url.path, exc_info=exc)
    return JSONResponse(status_code=400, content={"detail": "Invalid request"})


@app.exception_handler(FileNotFoundError)
async def file_not_found_handler(request: Request, exc: FileNotFoundError) -> JSONResponse:
    logger.warning("not_found path=%s", request.url.path, exc_info=exc)
    return JSONResponse(status_code=404, content={"detail": "Not found"})


@app.exception_handler(PermissionError)
async def permission_error_handler(request: Request, exc: PermissionError) -> JSONResponse:
    logger.warning("forbidden path=%s", request.url.path, exc_info=exc)
    return JSONResponse(status_code=403, content={"detail": "Forbidden"})


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError) -> JSONResponse:
    logger.error("internal_error path=%s", request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.exception_handler(SupabaseUnavailableError)
async def supabase_unavailable_handler(
    request: Request, exc: SupabaseUnavailableError
) -> JSONResponse:
    logger.warning("supabase_unavailable path=%s", request.url.path, exc_info=exc)
    return JSONResponse(status_code=503, content={"detail": "Service temporarily unavailable"})


@app.get(
    "/health",
    summary="Liveness check",
    description="Use to confirm the service is up.",
    tags=["health"],
)
async def health() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "parser_version": settings.parser_version,
    }


@app.get(
    "/health/ready",
    summary="Readiness check",
    description="Use before sending traffic to confirm Supabase and S3 are reachable.",
    tags=["health"],
)
async def health_ready() -> JSONResponse:
    settings = get_settings()
    checks = run_readiness_checks(settings)
    ready = checks.get("supabase") == "ok" and checks.get("s3") == "ok"
    status_code = 200 if ready else 503
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if ready else "not_ready",
            "parser_version": settings.parser_version,
            "checks": checks,
        },
    )


app.include_router(api_router)
