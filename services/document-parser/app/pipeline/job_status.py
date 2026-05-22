from datetime import UTC, datetime
from typing import Any

JOB_STATUS_PROCESSING = "processing"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_FAILED = "failed"


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def job_status_from_raw(raw: dict[str, Any] | None) -> str | None:
    if not raw:
        return None
    status = raw.get("job_status")
    if isinstance(status, str) and status in (
        JOB_STATUS_PROCESSING,
        JOB_STATUS_COMPLETED,
        JOB_STATUS_FAILED,
    ):
        return status
    return None


def processing_placeholder_raw(*, started_at: str | None = None) -> dict[str, Any]:
    return {
        "job_status": JOB_STATUS_PROCESSING,
        "started_at": started_at or utc_now_iso(),
    }


def failed_job_raw(*, error: str, started_at: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "job_status": JOB_STATUS_FAILED,
        "job_error": error,
        "failed_at": utc_now_iso(),
    }
    if started_at:
        payload["started_at"] = started_at
    return payload


def mark_raw_completed(raw: dict[str, Any]) -> dict[str, Any]:
    updated = dict(raw)
    updated["job_status"] = JOB_STATUS_COMPLETED
    updated.pop("job_error", None)
    updated["completed_at"] = utc_now_iso()
    return updated
