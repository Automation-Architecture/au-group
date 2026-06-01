"""Unit tests for pipeline/parse.py — the document_parse worker stage (KD-65)."""

from types import SimpleNamespace

import httpx
import pytest
from pipeline.parse import _FatalParseError, _is_transient
from pipeline.worker import _StageHandled

from pipeline import parse

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------

def _settings(**overrides):
    base = dict(
        supabase_url="https://sb.example.co",
        supabase_service_role_key="svc-key",
        supabase_http_timeout_sec=5.0,
        document_parser_url="http://parser.internal:8080",
        document_parser_api_key="parser-key",
        parse_poll_interval_sec=0.0,
        parse_poll_timeout_sec=10.0,
        parse_max_retries=3,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class _FakeResp:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            req = httpx.Request("GET", "http://x")
            raise httpx.HTTPStatusError(
                "err", request=req, response=httpx.Response(self.status_code, request=req)
            )


class _FakeClient:
    """Context-manager httpx.Client stand-in serving queued responses."""

    def __init__(self, queue):
        self._queue = queue

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def _next(self):
        item = self._queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def post(self, *a, **k):
        return self._next()

    def get(self, *a, **k):
        return self._next()


def _patch_client(monkeypatch, queue):
    """Patch parse.httpx.Client so each construction shares one response queue."""
    monkeypatch.setattr(parse.httpx, "Client", lambda *a, **k: _FakeClient(queue))


def _make_monotonic(values):
    it = iter(values)
    last = [0.0]

    def _m():
        try:
            last[0] = next(it)
        except StopIteration:
            last[0] += 1000.0
        return last[0]

    return _m


# ---------------------------------------------------------------------------
# _is_transient
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "exc,expected",
    [
        (httpx.ConnectError("x"), True),
        (httpx.ReadTimeout("x"), True),
        (
            httpx.HTTPStatusError(
                "x",
                request=httpx.Request("GET", "http://x"),
                response=httpx.Response(429, request=httpx.Request("GET", "http://x")),
            ),
            True,
        ),
        (
            httpx.HTTPStatusError(
                "x",
                request=httpx.Request("GET", "http://x"),
                response=httpx.Response(503, request=httpx.Request("GET", "http://x")),
            ),
            True,
        ),
        (
            httpx.HTTPStatusError(
                "x",
                request=httpx.Request("GET", "http://x"),
                response=httpx.Response(404, request=httpx.Request("GET", "http://x")),
            ),
            False,
        ),
        (ValueError("nope"), False),
    ],
)
def test_is_transient(exc, expected):
    assert _is_transient(exc) is expected


# ---------------------------------------------------------------------------
# _start_parse
# ---------------------------------------------------------------------------

def test_start_parse_success_returns_document_id(monkeypatch):
    _patch_client(monkeypatch, [_FakeResp(202, {"document_id": "doc-abc", "status": "processing"})])
    assert parse._start_parse("bk-1", "raw-documents/x/form-204.pdf", _settings()) == "doc-abc"


@pytest.mark.parametrize("code", [401, 403])
def test_start_parse_auth_is_fatal(monkeypatch, code):
    _patch_client(monkeypatch, [_FakeResp(code, {})])
    with pytest.raises(_FatalParseError, match="auth failed"):
        parse._start_parse("bk-1", "k", _settings())


def test_start_parse_409_is_fatal(monkeypatch):
    _patch_client(monkeypatch, [_FakeResp(409, {})])
    with pytest.raises(_FatalParseError, match="already processing"):
        parse._start_parse("bk-1", "k", _settings())


def test_start_parse_missing_document_id_is_fatal(monkeypatch):
    _patch_client(monkeypatch, [_FakeResp(202, {"status": "processing"})])
    with pytest.raises(_FatalParseError, match="missing document_id"):
        parse._start_parse("bk-1", "k", _settings())


def test_start_parse_500_raises_transient_httpstatuserror(monkeypatch):
    _patch_client(monkeypatch, [_FakeResp(500, {})])
    with pytest.raises(httpx.HTTPStatusError) as ei:
        parse._start_parse("bk-1", "k", _settings())
    assert _is_transient(ei.value)


# ---------------------------------------------------------------------------
# _poll_job
# ---------------------------------------------------------------------------

def test_poll_job_returns_completed(monkeypatch):
    _patch_client(monkeypatch, [_FakeResp(200, {"status": "completed", "manual_review_required": False})])
    monkeypatch.setattr(parse.time, "sleep", lambda *_: None)
    body = parse._poll_job("doc-1", _settings())
    assert body["status"] == "completed"


def test_poll_job_returns_failed(monkeypatch):
    _patch_client(monkeypatch, [_FakeResp(200, {"status": "failed", "error": "boom"})])
    monkeypatch.setattr(parse.time, "sleep", lambda *_: None)
    body = parse._poll_job("doc-1", _settings())
    assert body["status"] == "failed"


def test_poll_job_processing_then_completed(monkeypatch):
    _patch_client(
        monkeypatch,
        [
            _FakeResp(200, {"status": "processing"}),
            _FakeResp(200, {"status": "completed", "manual_review_required": False}),
        ],
    )
    monkeypatch.setattr(parse.time, "sleep", lambda *_: None)
    body = parse._poll_job("doc-1", _settings())
    assert body["status"] == "completed"


def test_poll_job_transient_error_then_completed(monkeypatch):
    _patch_client(
        monkeypatch,
        [httpx.ConnectError("blip"), _FakeResp(200, {"status": "completed"})],
    )
    monkeypatch.setattr(parse.time, "sleep", lambda *_: None)
    body = parse._poll_job("doc-1", _settings())
    assert body["status"] == "completed"


def test_poll_job_auth_is_fatal(monkeypatch):
    _patch_client(monkeypatch, [_FakeResp(401, {})])
    monkeypatch.setattr(parse.time, "sleep", lambda *_: None)
    with pytest.raises(_FatalParseError, match="auth failed"):
        parse._poll_job("doc-1", _settings())


def test_poll_job_timeout_is_fatal(monkeypatch):
    _patch_client(monkeypatch, [_FakeResp(200, {"status": "processing"})])
    monkeypatch.setattr(parse.time, "sleep", lambda *_: None)
    # deadline base=0 → deadline=10; first while-check=1 (<10, enter), next=100 (>=10, exit)
    monkeypatch.setattr(parse.time, "monotonic", _make_monotonic([0.0, 1.0, 100.0]))
    with pytest.raises(_FatalParseError, match="timed out"):
        parse._poll_job("doc-1", _settings(parse_poll_timeout_sec=10.0))


def test_poll_job_manual_review_is_terminal_even_when_pending(monkeypatch):
    # build_job_status can emit status="pending" paired with manual_review_required;
    # the poll must treat that as terminal rather than polling to timeout.
    _patch_client(monkeypatch, [_FakeResp(200, {"status": "pending", "manual_review_required": True})])
    monkeypatch.setattr(parse.time, "sleep", lambda *_: None)
    body = parse._poll_job("doc-1", _settings())
    assert body["manual_review_required"] is True


# ---------------------------------------------------------------------------
# process_job
# ---------------------------------------------------------------------------

def _job(**over):
    base = {"id": "job-1", "bankruptcy_id": "bk-1", "job_type": "document_parse"}
    base.update(over)
    return base


def test_process_job_completed_enqueues_enrich(monkeypatch):
    monkeypatch.setattr(parse, "get_pipeline_settings", lambda: _settings())
    monkeypatch.setattr(parse, "_get_case_number", lambda *a, **k: "1:26bk12345")
    monkeypatch.setattr(parse, "_start_parse", lambda *a, **k: "doc-1")
    monkeypatch.setattr(
        parse, "_poll_job", lambda *a, **k: {"status": "completed", "manual_review_required": False}
    )
    calls = {}
    monkeypatch.setattr(parse, "_enqueue_enrich", lambda bid, *a, **k: calls.setdefault("enrich", bid))
    monkeypatch.setattr(parse, "_fail_job", lambda *a, **k: calls.setdefault("fail", True))

    assert parse.process_job(_job()) is None
    assert calls["enrich"] == "bk-1"
    assert "fail" not in calls


def test_process_job_manual_review_fails_and_raises_stagehandled(monkeypatch):
    monkeypatch.setattr(parse, "get_pipeline_settings", lambda: _settings())
    monkeypatch.setattr(parse, "_get_case_number", lambda *a, **k: "1:26bk12345")
    monkeypatch.setattr(parse, "_start_parse", lambda *a, **k: "doc-1")
    monkeypatch.setattr(
        parse, "_poll_job", lambda *a, **k: {"status": "completed", "manual_review_required": True}
    )
    fail_calls = {}
    monkeypatch.setattr(
        parse, "_fail_job",
        lambda jid, msg, *a, **k: fail_calls.update(job_id=jid, msg=msg),
    )
    monkeypatch.setattr(parse, "_enqueue_enrich", lambda *a, **k: fail_calls.setdefault("enrich", True))

    with pytest.raises(_StageHandled):
        parse.process_job(_job())
    assert fail_calls["job_id"] == "job-1"
    assert fail_calls["msg"].startswith("manual_review_required:")
    assert "enrich" not in fail_calls  # enrich must NOT be enqueued on manual review


def test_process_job_pending_with_manual_review_routes_to_review(monkeypatch):
    # status="pending" + manual_review_required → manual-review path (checked before status)
    monkeypatch.setattr(parse, "get_pipeline_settings", lambda: _settings())
    monkeypatch.setattr(parse, "_get_case_number", lambda *a, **k: "1:26bk12345")
    monkeypatch.setattr(parse, "_start_parse", lambda *a, **k: "doc-1")
    monkeypatch.setattr(
        parse, "_poll_job", lambda *a, **k: {"status": "pending", "manual_review_required": True}
    )
    fail_calls = {}
    monkeypatch.setattr(parse, "_fail_job", lambda jid, msg, *a, **k: fail_calls.update(job_id=jid, msg=msg))
    monkeypatch.setattr(parse, "_enqueue_enrich", lambda *a, **k: fail_calls.setdefault("enrich", True))

    with pytest.raises(_StageHandled):
        parse.process_job(_job())
    assert fail_calls["msg"].startswith("manual_review_required:")
    assert "enrich" not in fail_calls


def test_process_job_parse_failed_raises_runtimeerror(monkeypatch):
    monkeypatch.setattr(parse, "get_pipeline_settings", lambda: _settings())
    monkeypatch.setattr(parse, "_get_case_number", lambda *a, **k: "1:26bk12345")
    monkeypatch.setattr(parse, "_start_parse", lambda *a, **k: "doc-1")
    monkeypatch.setattr(parse, "_poll_job", lambda *a, **k: {"status": "failed", "error": "ocr exploded"})
    monkeypatch.setattr(parse, "_enqueue_enrich", lambda *a, **k: None)

    with pytest.raises(RuntimeError, match="ocr exploded"):
        parse.process_job(_job())


def test_process_job_missing_bankruptcy_id_is_fatal(monkeypatch):
    monkeypatch.setattr(parse, "get_pipeline_settings", lambda: _settings())
    with pytest.raises(_FatalParseError, match="no bankruptcy_id"):
        parse.process_job(_job(bankruptcy_id=None))


def test_process_job_missing_api_key_is_fatal(monkeypatch):
    monkeypatch.setattr(parse, "get_pipeline_settings", lambda: _settings(document_parser_api_key=""))
    with pytest.raises(_FatalParseError, match="DOCUMENT_PARSER_API_KEY"):
        parse.process_job(_job())


def test_process_job_missing_case_number_row_is_fatal(monkeypatch):
    monkeypatch.setattr(parse, "get_pipeline_settings", lambda: _settings())
    monkeypatch.setattr(parse, "_get_case_number", lambda *a, **k: None)
    with pytest.raises(_FatalParseError, match="no bankruptcies row"):
        parse.process_job(_job())


def test_process_job_transient_start_then_success(monkeypatch):
    monkeypatch.setattr(parse, "get_pipeline_settings", lambda: _settings(parse_max_retries=3))
    monkeypatch.setattr(parse, "_get_case_number", lambda *a, **k: "1:26bk12345")
    attempts = {"n": 0}

    def _flaky_start(*a, **k):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise httpx.ConnectError("blip")
        return "doc-1"

    monkeypatch.setattr(parse, "_start_parse", _flaky_start)
    monkeypatch.setattr(parse, "_poll_job", lambda *a, **k: {"status": "completed", "manual_review_required": False})
    enq = {}
    monkeypatch.setattr(parse, "_enqueue_enrich", lambda bid, *a, **k: enq.setdefault("bid", bid))

    assert parse.process_job(_job()) is None
    assert attempts["n"] == 2
    assert enq["bid"] == "bk-1"


def test_process_job_start_exhausts_retries_raises_runtimeerror(monkeypatch):
    monkeypatch.setattr(parse, "get_pipeline_settings", lambda: _settings(parse_max_retries=2))
    monkeypatch.setattr(parse, "_get_case_number", lambda *a, **k: "1:26bk12345")
    monkeypatch.setattr(
        parse, "_start_parse",
        lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("down")),
    )
    with pytest.raises(RuntimeError, match="exhausted"):
        parse.process_job(_job())


def test_process_job_start_fatal_does_not_retry(monkeypatch):
    monkeypatch.setattr(parse, "get_pipeline_settings", lambda: _settings(parse_max_retries=3))
    monkeypatch.setattr(parse, "_get_case_number", lambda *a, **k: "1:26bk12345")
    attempts = {"n": 0}

    def _fatal_start(*a, **k):
        attempts["n"] += 1
        raise _FatalParseError("auth failed (401)")

    monkeypatch.setattr(parse, "_start_parse", _fatal_start)
    with pytest.raises(_FatalParseError, match="auth failed"):
        parse.process_job(_job())
    assert attempts["n"] == 1  # fatal short-circuits the retry loop
