"""Unit tests for pipeline/worker.py queue plumbing.

Regression cover for the 2026-08-13 production crash: au_group_claim_job is declared
`returns public.processing_jobs` (a composite), and PostgREST serialises a NULL composite
as a row of all-NULL columns rather than JSON null. The empty-queue guard treated that
truthy dict as a claimed job, dispatched it, hit `Unknown job_type: None`, and then PATCHed
`?id=eq.None` for a 400 — crashing every run where the queue was empty.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from pipeline import worker

SB_URL = "https://example.supabase.co"
SB_KEY = "service-role-key"
TIMEOUT = 5.0

# The all-NULL row PostgREST returns for a NULL composite (trimmed to the columns
# worker.py reads).
NULL_COMPOSITE_ROW = {
    "id": None,
    "job_type": None,
    "status": None,
    "bankruptcy_id": None,
    "started_at": None,
}


def _mock_transport(handler) -> Any:
    """Build a replacement for httpx.Client that routes through a MockTransport.

    `worker.httpx` is the httpx module itself, so monkeypatching `worker.httpx.Client`
    patches httpx globally — the factory must hold the real class captured here, or it
    recurses into itself.
    """
    real_client = httpx.Client

    def _factory(*args, **kwargs):
        return real_client(transport=httpx.MockTransport(handler))
    return _factory


# ---------------------------------------------------------------------------
# _claim_job
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw_body",
    [
        json.dumps(NULL_COMPOSITE_ROW),    # PostgREST NULL-composite -> row of nulls
        "null",                            # JSON null
        "[]",                              # empty array form
        json.dumps([NULL_COMPOSITE_ROW]),  # wrapped null-composite
    ],
    ids=["null_composite_row", "json_null", "empty_array", "wrapped_null_composite"],
)
def test_claim_job_returns_none_when_nothing_claimable(monkeypatch, raw_body):
    """An empty queue must yield None in every shape PostgREST can return it."""
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/rpc/au_group_claim_job")
        return httpx.Response(
            200, content=raw_body, headers={"Content-Type": "application/json"}
        )

    monkeypatch.setattr(worker.httpx, "Client", _mock_transport(handler))

    assert worker._claim_job("document_parse", SB_URL, SB_KEY, TIMEOUT) is None


def test_claim_job_returns_row_when_job_claimed(monkeypatch):
    """A real claim (non-null id) is passed through unchanged."""
    row = {
        "id": "1f0c2f5e-0000-4000-8000-000000000001",
        "job_type": "document_parse",
        "status": "running",
        "bankruptcy_id": "1f0c2f5e-0000-4000-8000-0000000000bb",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=row)

    monkeypatch.setattr(worker.httpx, "Client", _mock_transport(handler))

    assert worker._claim_job("document_parse", SB_URL, SB_KEY, TIMEOUT) == row


def test_claim_job_unwraps_single_element_array(monkeypatch):
    """Defensive: a row wrapped in an array is unwrapped, not dropped."""
    row = {"id": "1f0c2f5e-0000-4000-8000-000000000002", "job_type": "document_parse"}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[row])

    monkeypatch.setattr(worker.httpx, "Client", _mock_transport(handler))

    assert worker._claim_job("document_parse", SB_URL, SB_KEY, TIMEOUT) == row


# ---------------------------------------------------------------------------
# _patch_job guard
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("job_id", [None, ""], ids=["none", "empty_string"])
def test_patch_job_noops_on_missing_id(monkeypatch, job_id):
    """A falsy job_id must never reach PostgREST as ?id=eq.None (400)."""
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200)

    monkeypatch.setattr(worker.httpx, "Client", _mock_transport(handler))

    worker._patch_job(job_id, {"status": "failed"}, SB_URL, SB_KEY, TIMEOUT)

    assert calls == []


def test_fail_job_sends_expected_patch(monkeypatch):
    """A well-formed fail PATCHes the right row and truncates the error message."""
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = request.read().decode()
        return httpx.Response(200)

    monkeypatch.setattr(worker.httpx, "Client", _mock_transport(handler))

    worker._fail_job("job-123", "x" * 900, SB_URL, SB_KEY, TIMEOUT)

    assert "id=eq.job-123" in seen["url"]
    assert '"status":"failed"' in seen["body"].replace(" ", "")
    # error_message is capped at 500 chars.
    assert seen["body"].count("x") == 500


# ---------------------------------------------------------------------------
# _dispatch
# ---------------------------------------------------------------------------

class _Settings:
    skip_enrich = True
    skip_sf = True


def test_dispatch_rejects_unknown_job_type():
    """Unknown job types still raise — the guard belongs in _claim_job, not here."""
    with pytest.raises(ValueError, match="Unknown job_type"):
        worker._dispatch({"job_type": "nonsense"}, _Settings())


@pytest.mark.parametrize(
    "job_type", ["zoom_info_enrich", "salesforce_push"],
)
def test_dispatch_skips_blocked_stages(job_type):
    """SKIP_ENRICH / SKIP_SF requeue rather than dispatch during the parallel-run."""
    with pytest.raises(worker._SkipJob):
        worker._dispatch({"job_type": job_type, "bankruptcy_id": "b1"}, _Settings())
