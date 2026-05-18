from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import verify_auth
from app.models.schemas import JobStatusResponse, ReviewQueueItem, ReviewQueueResponse
from app.pipeline.router import DocumentPipeline

router = APIRouter(tags=["review"])


@router.get("/review-queue", response_model=ReviewQueueResponse)
async def list_review_queue(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = None,
    _auth=Depends(verify_auth),
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
    _auth=Depends(verify_auth),
) -> JobStatusResponse:
    pipeline = DocumentPipeline()
    status = pipeline.build_job_status(document_id)
    if not status:
        raise HTTPException(status_code=404, detail="Document not found")
    return status
