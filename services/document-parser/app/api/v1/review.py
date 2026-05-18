from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.security import verify_api_key
from app.models.schemas import FilingType, JobStatusResponse, ReviewQueueItem, ReviewQueueResponse
from app.pipeline.router import DocumentPipeline

router = APIRouter(tags=["review"])


@router.get("/review-queue", response_model=ReviewQueueResponse)
async def list_review_queue(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = None,
    _: str = Depends(verify_api_key),
) -> ReviewQueueResponse:
    pipeline = DocumentPipeline()
    rows, total = pipeline.list_review_queue(limit=limit, offset=offset, status=status)
    items = [
        ReviewQueueItem(
            id=UUID(str(row["id"])),
            bankruptcy_id=UUID(str(row["bankruptcy_id"]))
            if row.get("bankruptcy_id")
            else None,
            document_id=UUID(str(row["document_id"]))
            if row.get("document_id")
            else None,
            review_reason=row.get("review_reason", ""),
            status=row.get("status", "pending"),
            assigned_to=row.get("assigned_to"),
            created_at=str(row.get("created_at", "")),
        )
        for row in rows
    ]
    return ReviewQueueResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/jobs/{document_id}", response_model=JobStatusResponse)
async def get_job_status(
    document_id: UUID,
    _: str = Depends(verify_api_key),
) -> JobStatusResponse:
    pipeline = DocumentPipeline()
    row = pipeline.get_document_status(document_id)
    if not row:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Document not found")
    raw = row.get("raw_extraction")
    filing = row.get("filing_type")

    manual_review_required = row.get("manual_review_required")
    if manual_review_required is None and isinstance(raw, dict):
        manual_review_required = raw.get("manual_review_required")
    if manual_review_required is None:
        review_reason = row.get("review_reason")
        review_status = row.get("status")
        manual_review_required = bool(review_reason) or (
            review_status in {"pending", "assigned", "in_review"}
        )

    return JobStatusResponse(
        document_id=document_id,
        status="completed" if raw else "pending",
        parser_version=str(row.get("parser_version", "")),
        filing_type=FilingType(filing) if filing else None,
        manual_review_required=bool(manual_review_required),
        result=raw if isinstance(raw, dict) else None,
    )
