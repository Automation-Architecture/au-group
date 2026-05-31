"""Pipeline queue-draining worker — WP-01 (KD-58).

Invoked by the pipeline-worker Railway cron service every 30 minutes:
    python -m pipeline.worker

Drain loop:
  1. Reset stale jobs (au_group_fail_stale_processing_jobs).
  2. Claim one queued document_parse job at a time via au_group_claim_job.
  3. Dispatch to the stage module for that job type.
  4. Repeat until no queued jobs remain or the 25-minute time guard fires.
  5. Exit 0.

Railway cron service config (no port binding):
    rootDirectory:  services/document-parser
    startCommand:   python -m pipeline.worker
    schedule:       */30 * * * *  (every 30 minutes)

Skip flags (set as Railway env vars to disable blocked stages):
    SKIP_ENRICH=true   — skip zoom_info_enrich dispatch (ZoomInfo key not yet live)
    SKIP_SF=true       — skip salesforce_push dispatch (SF VPN/IP access not restored)

Stage dispatch is a forward-declaration pattern: each stage module is imported
lazily inside the dispatch function so the worker skeleton is independently
testable without requiring all stage modules to exist yet.

KD-65 (parse.py) will implement _dispatch_document_parse.
KD-67 (enrich.py) and KD-68 (salesforce.py) implement their stubs.
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import UTC, datetime
from typing import Any

import httpx

from pipeline.alerts import send_error_alert
from pipeline.settings import get_pipeline_settings

logger = logging.getLogger(__name__)

# Job types this worker drains (in priority order per spec §3.2).
_DRAIN_JOB_TYPES = ["document_parse", "zoom_info_enrich", "salesforce_push"]


# ---------------------------------------------------------------------------
# Supabase helpers (shared with intake — inline here to keep worker self-contained)
# ---------------------------------------------------------------------------

def _supabase_headers(key: str) -> dict[str, str]:
    return {
        "apikey":        key,
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
    }


def _reset_stale_jobs(supabase_url: str, key: str, timeout: float) -> int:
    """Call au_group_fail_stale_processing_jobs and return the count reset."""
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(
            f"{supabase_url.rstrip('/')}/rest/v1/rpc/au_group_fail_stale_processing_jobs",
            headers=_supabase_headers(key),
            json={"p_max_age": "24 hours"},
        )
        resp.raise_for_status()
    count = resp.json()
    logger.info("Stale-job reset: %s jobs failed", count)
    return int(count) if isinstance(count, (int, float)) else 0


def _claim_job(job_type: str, supabase_url: str, key: str, timeout: float) -> dict[str, Any] | None:
    """Call au_group_claim_job and return the claimed job row or None."""
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(
            f"{supabase_url.rstrip('/')}/rest/v1/rpc/au_group_claim_job",
            headers=_supabase_headers(key),
            json={"p_job_type": job_type},
        )
        resp.raise_for_status()
    return resp.json()  # returns the processing_jobs row dict or null


def _complete_job(job_id: str, supabase_url: str, key: str, timeout: float) -> None:
    with httpx.Client(timeout=timeout) as client:
        resp = client.patch(
            f"{supabase_url.rstrip('/')}/rest/v1/processing_jobs",
            headers={**_supabase_headers(key), "Prefer": "return=minimal"},
            params={"id": f"eq.{job_id}"},
            json={"status": "completed", "completed_at": datetime.now(tz=UTC).isoformat()},
        )
        resp.raise_for_status()


def _fail_job(job_id: str, error_msg: str, supabase_url: str, key: str, timeout: float) -> None:
    with httpx.Client(timeout=timeout) as client:
        resp = client.patch(
            f"{supabase_url.rstrip('/')}/rest/v1/processing_jobs",
            headers={**_supabase_headers(key), "Prefer": "return=minimal"},
            params={"id": f"eq.{job_id}"},
            json={"status": "failed", "completed_at": datetime.now(tz=UTC).isoformat(), "error_message": error_msg[:500]},
        )
        resp.raise_for_status()


def _requeue_job(job_id: str, supabase_url: str, key: str, timeout: float) -> None:
    """Release a claimed job back to queued so it can be retried later."""
    with httpx.Client(timeout=timeout) as client:
        resp = client.patch(
            f"{supabase_url.rstrip('/')}/rest/v1/processing_jobs",
            headers={**_supabase_headers(key), "Prefer": "return=minimal"},
            params={"id": f"eq.{job_id}"},
            json={"status": "queued", "started_at": None},
        )
        resp.raise_for_status()


# ---------------------------------------------------------------------------
# Stage dispatch
# ---------------------------------------------------------------------------

class _SkipJob(Exception):
    """Raised by _dispatch when a skip flag is active; the drain loop requeues the job."""

def _dispatch(job: dict[str, Any], settings: Any) -> None:
    """Dispatch the claimed job to the appropriate stage module.

    Each stage module is imported lazily — the worker skeleton runs even if
    parse.py / enrich.py / salesforce.py do not yet exist.
    """
    job_type    = job.get("job_type", "")
    bankruptcy_id = job.get("bankruptcy_id")

    if job_type == "document_parse":
        try:
            from pipeline import parse  # type: ignore[import]
        except ImportError:
            raise NotImplementedError(
                "pipeline.parse not yet implemented (KD-65). "
                "Job requeued — will be claimed on next worker run when KD-65 lands."
            )
        parse.process_job(job)

    elif job_type == "zoom_info_enrich":
        if settings.skip_enrich:
            logger.info("SKIP_ENRICH active — requeueing zoom_info_enrich for %s", bankruptcy_id)
            raise _SkipJob("SKIP_ENRICH active — will retry when stage is enabled")
        try:
            from pipeline import enrich  # type: ignore[import]
        except ImportError:
            raise NotImplementedError("pipeline.enrich not yet implemented (KD-67)")
        enrich.process_job(job)

    elif job_type == "salesforce_push":
        if settings.skip_sf:
            logger.info("SKIP_SF active — requeueing salesforce_push for %s", bankruptcy_id)
            raise _SkipJob("SKIP_SF active — will retry when stage is enabled")
        try:
            from pipeline import salesforce  # type: ignore[import]
        except ImportError:
            raise NotImplementedError("pipeline.salesforce not yet implemented (KD-68)")
        salesforce.process_job(job)

    else:
        raise ValueError(f"Unknown job_type: {job_type!r}")


# ---------------------------------------------------------------------------
# Drain loop
# ---------------------------------------------------------------------------

def run() -> int:
    """Drain the processing_jobs queue. Returns the number of jobs processed."""
    settings    = get_pipeline_settings()
    sb_url      = settings.supabase_url
    sb_key      = settings.supabase_service_role_key
    sb_t        = settings.supabase_http_timeout_sec
    deadline    = time.monotonic() + settings.worker_max_runtime_sec
    jobs_done   = 0

    # 1. Reset stale jobs before claiming.
    try:
        _reset_stale_jobs(sb_url, sb_key, sb_t)
    except Exception as exc:
        logger.error("Stale-job reset failed: %s", exc)
        send_error_alert(
            stage="worker.py — stale-job reset",
            error=str(exc),
            bot_token=settings.slack_bot_token,
            channel_id=settings.slack_channel_id,
        )
        # Non-fatal — continue draining.

    # 2. Drain each job type in priority order.
    for job_type in _DRAIN_JOB_TYPES:
        if time.monotonic() >= deadline:
            logger.warning("Time guard reached (%ds) — exiting before %s drain", settings.worker_max_runtime_sec, job_type)
            break

        while time.monotonic() < deadline:
            try:
                job = _claim_job(job_type, sb_url, sb_key, sb_t)
            except Exception as exc:
                logger.error("claim_job(%s) failed: %s", job_type, exc)
                send_error_alert(
                    stage=f"worker.py — claim {job_type}",
                    error=str(exc),
                    bot_token=settings.slack_bot_token,
                    channel_id=settings.slack_channel_id,
                )
                break  # move to next job type

            if not job:
                logger.debug("No queued %s jobs — moving on", job_type)
                break

            job_id        = job.get("id", "?")
            bankruptcy_id = job.get("bankruptcy_id")
            logger.info("Processing %s job %s (bankruptcy=%s)", job_type, job_id, bankruptcy_id)

            try:
                _dispatch(job, settings)
                _complete_job(job_id, sb_url, sb_key, sb_t)
                jobs_done += 1
                logger.info("Completed %s job %s", job_type, job_id)

            except _SkipJob as exc:
                # Skip flag active — release job back to queued so it runs when the stage is live.
                logger.info("%s — requeueing job %s", exc, job_id)
                _requeue_job(job_id, sb_url, sb_key, sb_t)
                break  # all remaining jobs of this type will also be skipped

            except NotImplementedError as exc:
                # Stage module not yet built — requeue so it is retried when KD-65/67/68 land.
                logger.info("%s — requeueing job %s", exc, job_id)
                _requeue_job(job_id, sb_url, sb_key, sb_t)

            except Exception as exc:
                logger.error("%s job %s failed: %s", job_type, job_id, exc)
                _fail_job(job_id, str(exc), sb_url, sb_key, sb_t)
                send_error_alert(
                    stage=f"worker.py — {job_type}",
                    error=str(exc),
                    bankruptcy_id=str(bankruptcy_id) if bankruptcy_id else None,
                    bot_token=settings.slack_bot_token,
                    channel_id=settings.slack_channel_id,
                )

    return jobs_done


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    count = run()
    logger.info("Worker done: %d jobs processed", count)
    sys.exit(0)


if __name__ == "__main__":
    main()
