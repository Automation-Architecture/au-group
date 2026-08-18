"""Pipeline parse stage — WP-06 (KD-65).

The worker dispatches ``document_parse`` jobs here.  For each job this stage:

  1. Resolves the bankruptcy's ``case_number`` → Form 204 S3 key.
  2. POSTs ``/api/v1/parse/document`` (``async_mode``) to the document-parser
     web service, which OCRs/parses the Form 204 in the background.
  3. Polls ``GET /api/v1/jobs/{document_id}`` until the parse reaches a terminal
     state (``completed``/``failed``, or ``manual_review_required`` set — the
     latter is treated as terminal so a "pending" status that pairs with it does
     not poll to timeout; see ``build_job_status`` in app.pipeline.router).
  4. Acts on the outcome (manual review is checked first, before status):
       - ``manual_review_required`` → the document-parser has routed the doc to
         its own review queue (review.py apply/resolve).  Mark this job ``failed``
         with a ``manual_review_required:`` error_message and raise
         :class:`pipeline.worker._StageHandled` so the drain loop neither
         completes, requeues, nor fires a generic Slack alert.
       - ``completed`` (no manual review) → enqueue the next stage
         (``zoom_info_enrich``) and return normally; the worker then marks the
         ``document_parse`` job completed.
       - ``failed`` → raise ``RuntimeError`` so the worker marks the job failed
         and alerts.

The document-parser service itself persists the parsed creditor matrix; this
stage only orchestrates the parse and hands off to enrichment.

Note (KD-65 scope): a debtor routed to manual review will not appear in the
daily creditor report until a human resolves it via the document-parser review
queue; nothing proactively notifies the operator.  Acceptable for MVP — the
failed-job row with the ``manual_review_required:`` prefix is the signal.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

import httpx

# Single source of truth for the Form 204 S3 key layout — never re-implement the
# safe-substitution regex here; if it drifts from intake's, every parse looks for
# the wrong key and fails silently.
from pipeline.intake import _form_204_s3_key
from pipeline.settings import PipelineSettings, get_pipeline_settings
from pipeline.worker import _StageHandled

logger = logging.getLogger(__name__)

# Terminal HTTP JobStatusResponse.status values (app/pipeline/job_status.py).
# Non-terminal values ("processing", "queued", and the "pending" that
# build_job_status emits) simply continue the poll loop; manual_review_required
# is handled as a terminal signal independently of status.
_JOB_COMPLETED = "completed"
_JOB_FAILED = "failed"


class _FatalParseError(RuntimeError):
    """Non-retryable parse failure (missing config/data, auth, non-429 4xx)."""


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _supabase_headers(key: str) -> dict[str, str]:
    return {
        "apikey":        key,
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
    }


def _parser_headers(api_key: str) -> dict[str, str]:
    return {"X-API-Key": api_key, "Content-Type": "application/json"}


def _is_transient(exc: Exception) -> bool:
    """Network errors and 429/5xx responses are worth retrying; other 4xx are not."""
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code == 429 or 500 <= code < 600
    return isinstance(exc, httpx.RequestError)


# ---------------------------------------------------------------------------
# Supabase reads / writes
# ---------------------------------------------------------------------------

def _get_case_number(
    bankruptcy_id: str,
    supabase_url: str,
    key: str,
    timeout: float,
) -> str | None:
    """Return the bankruptcy's case_number, or None if no row matches."""
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(
            f"{supabase_url.rstrip('/')}/rest/v1/bankruptcies",
            headers=_supabase_headers(key),
            params={"select": "case_number", "id": f"eq.{bankruptcy_id}", "limit": "1"},
        )
        resp.raise_for_status()
    rows = resp.json()
    if isinstance(rows, list) and rows:
        return rows[0].get("case_number")
    return None


def _fail_job(
    job_id: str,
    error_msg: str,
    supabase_url: str,
    key: str,
    timeout: float,
) -> None:
    """Mark a processing_jobs row failed with an explanatory message."""
    with httpx.Client(timeout=timeout) as client:
        resp = client.patch(
            f"{supabase_url.rstrip('/')}/rest/v1/processing_jobs",
            headers={**_supabase_headers(key), "Prefer": "return=minimal"},
            params={"id": f"eq.{job_id}"},
            json={
                "status":        "failed",
                "completed_at":  datetime.now(tz=UTC).isoformat(),
                "error_message": error_msg[:500],
            },
        )
        resp.raise_for_status()


def _enqueue_enrich(
    bankruptcy_id: str,
    supabase_url: str,
    key: str,
    timeout: float,
) -> None:
    """Enqueue the zoom_info_enrich stage. No-ops if already queued/running."""
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(
            f"{supabase_url.rstrip('/')}/rest/v1/rpc/au_group_enqueue_job",
            headers=_supabase_headers(key),
            json={"p_bankruptcy_id": bankruptcy_id, "p_job_type": "zoom_info_enrich"},
        )
        resp.raise_for_status()
    logger.debug("enqueue zoom_info_enrich for %s", bankruptcy_id)


# ---------------------------------------------------------------------------
# Document-parser HTTP calls
# ---------------------------------------------------------------------------

# Every document this stage parses is a Form 204 that intake retrieved, so the
# filing type is known up front — tell the parser instead of making it guess.
# Without the hint, classify_filing_type() scores anchor phrases and picks the
# highest: on a COMBINED voluntary petition (which is what RECAP returns for most
# cases, since the 20-largest list is filed inside the petition rather than as a
# standalone document) the Form 201 anchors outscore the creditor-matrix ones,
# the document routes to Form 201 extraction, and ZERO creditors come out — with
# no error anywhere, because parsing a petition as a petition "succeeded".
# Value is FilingType.CREDITOR_MATRIX; kept as a literal so the cron entrypoints
# do not import the FastAPI app package. (KD-82)
_DOCKET_HINT = "CREDITOR_MATRIX"


def _start_parse(
    bankruptcy_id: str,
    s3_key: str,
    settings: PipelineSettings,
) -> str:
    """POST /api/v1/parse/document (async) and return the document_id to poll.

    Raises _FatalParseError directly on 401/403 auth, 409 already-processing, and
    missing document_id. Other non-2xx responses propagate from raise_for_status()
    as httpx.HTTPStatusError; the caller's retry loop then classifies them via
    _is_transient (429/5xx → retry, other 4xx → fatal). Network errors likewise
    propagate as httpx.RequestError for the caller to retry.
    """
    url = f"{settings.document_parser_url.rstrip('/')}/api/v1/parse/document"
    with httpx.Client(timeout=settings.supabase_http_timeout_sec) as client:
        resp = client.post(
            url,
            headers=_parser_headers(settings.document_parser_api_key),
            json={
                "bankruptcy_id": bankruptcy_id,
                "s3_key": s3_key,
                "async_mode": True,
                "docket_hint": _DOCKET_HINT,
            },
        )
    if resp.status_code in (401, 403):
        raise _FatalParseError(f"document-parser auth failed ({resp.status_code})")
    # 409 = doc already processing. With a single sequential worker this should
    # not occur; treat it as fatal for this job rather than spin (the duplicate
    # parse owns the document_id we'd need to poll).
    if resp.status_code == 409:
        raise _FatalParseError("document-parser reports document already processing (409)")
    resp.raise_for_status()  # 429/5xx → HTTPStatusError (transient); other 4xx propagate
    body = resp.json()
    document_id = body.get("document_id")
    if not document_id:
        raise _FatalParseError("parse/document response missing document_id")
    return str(document_id)


def _poll_job(document_id: str, settings: PipelineSettings) -> dict[str, Any]:
    """Poll GET /api/v1/jobs/{document_id} until terminal or timeout.

    Returns the terminal JobStatusResponse body. Reads the TOP-LEVEL ``status``
    and ``manual_review_required`` fields (not nested under ``result``). Terminal
    when status is ``completed``/``failed`` OR ``manual_review_required`` is set
    (the parser has already decided, and a "pending" status can pair with it).
    A single Client is reused across iterations. Transient GET failures are
    tolerated within the poll timeout window. Raises _FatalParseError on timeout.
    """
    url = f"{settings.document_parser_url.rstrip('/')}/api/v1/jobs/{document_id}"
    headers = _parser_headers(settings.document_parser_api_key)
    deadline = time.monotonic() + settings.parse_poll_timeout_sec

    with httpx.Client(timeout=settings.supabase_http_timeout_sec) as client:
        while time.monotonic() < deadline:
            try:
                resp = client.get(url, headers=headers)
                if resp.status_code in (401, 403):
                    raise _FatalParseError(f"document-parser auth failed ({resp.status_code})")
                resp.raise_for_status()
                body = resp.json()
            except _FatalParseError:
                raise
            except Exception as exc:  # noqa: BLE001 — transient network/5xx; retry until deadline
                if not _is_transient(exc):
                    raise _FatalParseError(f"job-status poll failed: {exc}") from exc
                logger.warning("Transient poll error for %s (%s) — retrying", document_id, exc)
                time.sleep(settings.parse_poll_interval_sec)
                continue

            status = body.get("status")
            if status in (_JOB_COMPLETED, _JOB_FAILED) or body.get("manual_review_required"):
                return body
            # processing / queued / pending (non-terminal) → keep polling
            time.sleep(settings.parse_poll_interval_sec)

    raise _FatalParseError(
        f"parse timed out after {settings.parse_poll_timeout_sec:.0f}s (document_id={document_id})"
    )


# ---------------------------------------------------------------------------
# Worker entry point
# ---------------------------------------------------------------------------

def process_job(job: dict[str, Any]) -> None:
    """Process one document_parse job. Called by worker._dispatch.

    Normal return → worker marks the job completed.
    _StageHandled  → stage already set terminal state (manual review).
    RuntimeError   → worker marks the job failed + alerts.
    """
    settings = get_pipeline_settings()
    sb_url = settings.supabase_url
    sb_key = settings.supabase_service_role_key
    sb_t = settings.supabase_http_timeout_sec

    job_id = str(job.get("id", "?"))
    bankruptcy_id = job.get("bankruptcy_id")
    if not bankruptcy_id:
        raise _FatalParseError(f"document_parse job {job_id} has no bankruptcy_id")
    if not settings.document_parser_api_key:
        raise _FatalParseError("DOCUMENT_PARSER_API_KEY is not set")

    case_number = _get_case_number(str(bankruptcy_id), sb_url, sb_key, sb_t)
    if not case_number:
        raise _FatalParseError(f"no bankruptcies row for {bankruptcy_id}")
    s3_key = _form_204_s3_key(case_number)

    # Start the async parse, retrying transient failures.
    document_id: str | None = None
    last_exc: Exception | None = None
    for attempt in range(1, settings.parse_max_retries + 1):
        try:
            document_id = _start_parse(str(bankruptcy_id), s3_key, settings)
            break
        except _FatalParseError:
            raise
        except Exception as exc:  # noqa: BLE001 — classify transient vs fatal
            last_exc = exc
            if not _is_transient(exc):
                raise _FatalParseError(f"parse start failed: {exc}") from exc
            logger.warning("parse start attempt %d/%d failed (%s) — retrying",
                           attempt, settings.parse_max_retries, exc)
    if document_id is None:
        raise RuntimeError(f"parse start exhausted {settings.parse_max_retries} retries: {last_exc}")

    body = _poll_job(document_id, settings)
    status = body.get("status")
    manual_review = bool(body.get("manual_review_required"))

    # Manual review is checked first: the parser has flagged the doc for a human,
    # which can pair with either a "completed" or a "pending" status.
    if manual_review:
        msg = f"manual_review_required: parse flagged document_id={document_id} for human review"
        _fail_job(job_id, msg, sb_url, sb_key, sb_t)
        logger.info("parse → manual review for %s (document_id=%s)", bankruptcy_id, document_id)
        raise _StageHandled(msg)

    if status == _JOB_COMPLETED:
        _enqueue_enrich(str(bankruptcy_id), sb_url, sb_key, sb_t)
        logger.info("parse completed for %s (document_id=%s) — enqueued enrich",
                    bankruptcy_id, document_id)
        return  # worker marks job completed

    # status == failed (or unexpected terminal value)
    err = body.get("error") or f"parse failed (status={status!r})"
    raise RuntimeError(f"document-parser parse failed for {bankruptcy_id}: {err}")
