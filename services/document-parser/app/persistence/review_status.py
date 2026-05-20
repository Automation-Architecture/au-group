"""Allowed manual_review_queue status filter values for PostgREST queries."""

REVIEW_QUEUE_STATUSES = frozenset({"pending", "in_review", "resolved", "rejected"})


def validate_review_queue_status(status: str | None) -> str | None:
    if status is None:
        return None
    if status not in REVIEW_QUEUE_STATUSES:
        raise ValueError(
            f"Invalid status filter; allowed: {', '.join(sorted(REVIEW_QUEUE_STATUSES))}"
        )
    return status
