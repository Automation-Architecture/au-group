import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.core.security import verify_auth
from app.models.schemas import (
    JobStatusResponse,
    ResolveReviewRequest,
    ResolveReviewResponse,
    ReviewQueueItem,
    ReviewQueueResponse,
)
from app.pipeline.router import DocumentPipeline

router = APIRouter(tags=["review"])
logger = logging.getLogger(__name__)

_review_rate_limit = lambda: get_settings().rate_limit_review  # noqa: E731


@router.get(
    "/review-queue",
    response_model=ReviewQueueResponse,
    summary="Review queue",
    description="Use to list filings that need a person to review before proceeding.",
)
@limiter.limit(_review_rate_limit)
async def list_review_queue(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = None,
    _auth=Depends(verify_auth),
) -> ReviewQueueResponse:
    pipeline = DocumentPipeline()
    try:
        rows, total = pipeline.list_review_queue(limit=limit, offset=offset, status=status)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    items = [
        ReviewQueueItem(
            id=UUID(str(row["id"])),
            bankruptcy_id=UUID(str(row["bankruptcy_id"])) if row.get("bankruptcy_id") else None,
            document_id=UUID(str(row["document_id"])) if row.get("document_id") else None,
            review_reason=row.get("review_reason", ""),
            status=row.get("status", "pending"),
            assigned_to=row.get("assigned_to"),
            created_at=str(row.get("created_at", "")),
        )
        for row in rows
    ]
    return ReviewQueueResponse(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/jobs/{document_id}",
    response_model=JobStatusResponse,
    summary="Job status",
    description="Use to check whether a background parse has finished (after parse/document with async_mode).",
)
@limiter.limit(_review_rate_limit)
async def get_job_status(
    request: Request,
    document_id: UUID,
    _auth=Depends(verify_auth),
) -> JobStatusResponse:
    pipeline = DocumentPipeline()
    status = pipeline.build_job_status(document_id)
    if not status:
        raise HTTPException(status_code=404, detail="Document not found")
    return status


@router.post(
    "/review/{review_id}/resolve",
    response_model=ResolveReviewResponse,
    summary="Resolve review",
    description="Use to mark a review-queue item as done after a human has checked it.",
)
@limiter.limit(_review_rate_limit)
async def resolve_review(
    request: Request,
    review_id: UUID,
    body: ResolveReviewRequest | None = None,
    _auth=Depends(verify_auth),
) -> ResolveReviewResponse:
    pipeline = DocumentPipeline()
    try:
        result = pipeline.resolve_manual_review(
            review_id,
            resolved_by=body.resolved_by if body else None,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Review item not found") from exc
    except RuntimeError as exc:
        logger.exception("resolve_manual_review_failed review_id=%s", review_id)
        raise HTTPException(status_code=503, detail="Service temporarily unavailable") from exc

    bankruptcy_flag = result.get("bankruptcy_manual_review_required")
    return ResolveReviewResponse(
        review_id=UUID(str(result["review_id"])),
        document_id=UUID(str(result["document_id"])) if result.get("document_id") else None,
        bankruptcy_id=UUID(str(result["bankruptcy_id"])) if result.get("bankruptcy_id") else None,
        status=str(result.get("status", "resolved")),
        bankruptcy_manual_review_required=bool(bankruptcy_flag)
        if bankruptcy_flag is not None
        else None,
    )
