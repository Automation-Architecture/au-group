"""Unit tests for pipeline/enrich.py — the zoom_info_enrich stage (KD-67).

A fake ZoomInfo client is injected; Supabase reads/writes are monkeypatched via
the module httpx idiom. No live ZoomInfo or Supabase is hit.
"""

import httpx
import pytest
from pipeline.enrich import (
    Enricher,
    EnrichResult,
    ZoomInfoClient,
    _classify_tier,
)

from pipeline import enrich

# ---------------------------------------------------------------------------
# Tier classification
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("revenue_k,employees,expected", [
    (2_000_000, None, 1),       # $2B → Enterprise
    (None, 8000, 1),            # 8k employees → Enterprise
    (50_000, 6000, 1),          # SMB revenue but Enterprise headcount (OR rule)
    (500_000, None, 2),         # $500M → Mid-Market
    (None, 1200, 2),            # 1.2k employees → Mid-Market
    (50_000, 100, 3),           # small → SMB
    (None, None, None),         # no signal → unknown
    (0, 0, 3),                  # zeros are signals → SMB (not "unknown")
    (True, None, None),         # bool is not a number
])
def test_classify_tier(revenue_k, employees, expected):
    assert _classify_tier(revenue_k, employees) == expected


# ---------------------------------------------------------------------------
# ZoomInfoClient.enrich_company — response parsing
# ---------------------------------------------------------------------------

class _FakeResp:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            req = httpx.Request("POST", "http://x")
            raise httpx.HTTPStatusError("e", request=req,
                                        response=httpx.Response(self.status_code, request=req))


class _FakeClient:
    def __init__(self, queue):
        self._q = queue

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, *a, **k):
        item = self._q.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _patch_httpx(monkeypatch, queue):
    monkeypatch.setattr(enrich.httpx, "Client", lambda *a, **k: _FakeClient(queue))
    monkeypatch.setattr(enrich, "_RETRY_BASE_SEC", 0.0)


def _zi():
    return ZoomInfoClient("tok", "https://api.zoominfo.com/gtm", 5.0, "FULL_MATCH")


def test_enrich_company_full_match(monkeypatch):
    resp = _FakeResp(json_data={"data": [{
        "id": "344589814", "type": "Company",
        "attributes": {"name": "ZoomInfo", "revenue": 245000, "employeeCount": 4200},
        "meta": {"matchStatus": "FULL_MATCH"}}]})
    _patch_httpx(monkeypatch, [resp])
    r = _zi().enrich_company("Zoominfo Inc", "MA")
    assert r.matched and r.company_id == "344589814" and r.canonical_name == "ZoomInfo"
    assert r.revenue == 245000 and r.employee_count == 4200


def test_enrich_company_no_match_empty_data(monkeypatch):
    _patch_httpx(monkeypatch, [_FakeResp(json_data={"data": []})])
    assert _zi().enrich_company("Nobody", None).matched is False


def test_enrich_company_below_match_floor(monkeypatch):
    resp = _FakeResp(json_data={"data": [{
        "id": "1", "attributes": {"name": "X"}, "meta": {"matchStatus": "NO_MATCH"}}]})
    _patch_httpx(monkeypatch, [resp])
    assert _zi().enrich_company("X", None).matched is False


def test_enrich_company_retries_on_429(monkeypatch):
    req = httpx.Request("POST", "http://x")
    err = httpx.HTTPStatusError("429", request=req, response=httpx.Response(429, request=req))
    ok = _FakeResp(json_data={"data": [{"id": "9", "attributes": {"name": "Y", "revenue": 10},
                                        "meta": {"matchStatus": "FULL_MATCH"}}]})
    _patch_httpx(monkeypatch, [err, ok])  # first 429, then success
    assert _zi().enrich_company("Y", None).company_id == "9"


# ---------------------------------------------------------------------------
# Enricher.enrich_bankruptcy — persistence, no-match, isolation
# ---------------------------------------------------------------------------

class _FakeZI:
    def __init__(self, by_name):
        self._by_name = by_name  # name → EnrichResult or Exception

    def enrich_company(self, name, state):
        out = self._by_name.get(name)
        if isinstance(out, Exception):
            raise out
        return out or EnrichResult(matched=False)


@pytest.fixture
def _writes(monkeypatch):
    rec = {"patch": [], "zid": [], "contact": []}
    monkeypatch.setattr(enrich, "_patch_creditor", lambda cid, f, *a: rec["patch"].append((cid, f)))
    monkeypatch.setattr(enrich, "_set_zoominfo_id", lambda cid, c, *a: rec["zid"].append((cid, c)))
    monkeypatch.setattr(enrich, "_upsert_contact",
                        lambda cid, fn, rev, emp, *a: rec["contact"].append((cid, fn, rev, emp)))
    return rec


def _creditor(**over):
    base = {"creditor_id": "c1", "creditor_name": "Cf Logistics",
            "normalized_name": "CF LOGISTICS", "creditor_state": "NJ"}
    base.update(over)
    return base


def _enricher(zi):
    return Enricher(zi, "https://sb.example.co", "k", 5.0)


def test_enrich_bankruptcy_full_match_persists(_writes):
    zi = _FakeZI({"CF LOGISTICS": EnrichResult(
        matched=True, company_id="999", canonical_name="CF Logistics LLC",
        revenue=2_000_000, employee_count=6000)})
    s = _enricher(zi).enrich_bankruptcy([_creditor()])
    assert s.enriched == 1 and s.no_match == 0 and not s.failed
    assert _writes["patch"] == [("c1", {"company_tier": 1, "normalized_name": "CF Logistics LLC"})]
    assert _writes["zid"] == [("c1", "999")]
    assert _writes["contact"][0][:2] == ("c1", "CF Logistics LLC")


def test_enrich_bankruptcy_no_match_writes_nothing(_writes):
    zi = _FakeZI({"CF LOGISTICS": EnrichResult(matched=False)})
    s = _enricher(zi).enrich_bankruptcy([_creditor()])
    assert s.no_match == 1 and s.enriched == 0
    assert not _writes["patch"] and not _writes["zid"] and not _writes["contact"]


def test_enrich_bankruptcy_match_without_tier_signal(_writes):
    # matched but no revenue/employees → no company_tier, still sets name + contact
    zi = _FakeZI({"CF LOGISTICS": EnrichResult(matched=True, company_id="5",
                                               canonical_name="CF Logistics", revenue=None, employee_count=None)})
    _enricher(zi).enrich_bankruptcy([_creditor()])
    assert _writes["patch"] == [("c1", {"normalized_name": "CF Logistics"})]  # no company_tier key
    assert _writes["contact"][0][2:] == (None, None)


def test_enrich_bankruptcy_isolates_failures(_writes):
    zi = _FakeZI({
        "CF LOGISTICS": EnrichResult(matched=True, company_id="1", canonical_name="A", revenue=10),
        "OTHER CO": httpx.ConnectError("boom")})
    s = _enricher(zi).enrich_bankruptcy([_creditor(), _creditor(creditor_id="c2", normalized_name="OTHER CO")])
    assert s.enriched == 1 and s.failed == ["c2"]


# ---------------------------------------------------------------------------
# process_job orchestration + guard
# ---------------------------------------------------------------------------

def _settings(**over):
    from types import SimpleNamespace
    base = dict(supabase_url="https://sb.example.co", supabase_service_role_key="k",
                supabase_http_timeout_sec=5.0, zoominfo_client_id="id", zoominfo_client_secret="sec",
                zoominfo_base_url="https://api.zoominfo.com/gtm", zoominfo_timeout_sec=5.0,
                zoominfo_match_status="FULL_MATCH", slack_bot_token="xoxb", slack_channel_id="C1")
    base.update(over)
    return SimpleNamespace(**base)


def test_process_job_guard_missing_creds(monkeypatch):
    monkeypatch.setattr(enrich, "get_pipeline_settings",
                        lambda: _settings(zoominfo_client_id="", zoominfo_client_secret=""))
    with pytest.raises(enrich._FatalEnrichError):
        enrich.process_job({"id": "j1", "bankruptcy_id": "b1"})


def test_process_job_no_bankruptcy_id(monkeypatch):
    monkeypatch.setattr(enrich, "get_pipeline_settings", lambda: _settings())
    with pytest.raises(enrich._FatalEnrichError):
        enrich.process_job({"id": "j1"})


def test_process_job_no_creditors_skips_client(monkeypatch):
    monkeypatch.setattr(enrich, "get_pipeline_settings", lambda: _settings())
    monkeypatch.setattr(enrich, "_list_company_creditors", lambda *a: [])
    built = {"v": False}
    monkeypatch.setattr(enrich, "build_zoominfo_client", lambda s: built.__setitem__("v", True))
    enrich.process_job({"id": "j1", "bankruptcy_id": "b1"})  # returns
    assert built["v"] is False  # short-circuits before auth


def test_process_job_full_enqueues_salesforce(monkeypatch):
    monkeypatch.setattr(enrich, "get_pipeline_settings", lambda: _settings())
    monkeypatch.setattr(enrich, "_list_company_creditors", lambda *a: [_creditor()])
    monkeypatch.setattr(enrich, "build_zoominfo_client",
                        lambda s: _FakeZI({"CF LOGISTICS": EnrichResult(matched=False)}))
    monkeypatch.setattr(enrich, "_patch_creditor", lambda *a: None)
    enq = []
    monkeypatch.setattr(enrich, "_enqueue_salesforce_push", lambda bid, *a: enq.append(bid))
    enrich.process_job({"id": "j1", "bankruptcy_id": "b1"})
    assert enq == ["b1"]  # salesforce_push enqueued even on all-no-match


def test_process_job_partial_failure_alerts(monkeypatch):
    monkeypatch.setattr(enrich, "get_pipeline_settings", lambda: _settings())
    monkeypatch.setattr(enrich, "_list_company_creditors", lambda *a: [_creditor()])
    monkeypatch.setattr(enrich, "build_zoominfo_client",
                        lambda s: _FakeZI({"CF LOGISTICS": httpx.ConnectError("down")}))
    monkeypatch.setattr(enrich, "_enqueue_salesforce_push", lambda *a: None)
    alerts = []
    monkeypatch.setattr(enrich, "send_error_alert", lambda **kw: alerts.append(kw))
    enrich.process_job({"id": "j1", "bankruptcy_id": "b1"})
    assert len(alerts) == 1 and "c1" in alerts[0]["error"]


# ---------------------------------------------------------------------------
# HTTP-shaping helpers: token auth + idempotent contact write
# ---------------------------------------------------------------------------

class _RecordingClient:
    """Records (method, url, kwargs) and returns queued responses in order."""

    def __init__(self, queue):
        self._q = queue
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def _next(self, method, url, **kw):
        self.calls.append((method, url, kw))
        item = self._q.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def post(self, url, **kw):
        return self._next("POST", url, **kw)

    def delete(self, url, **kw):
        return self._next("DELETE", url, **kw)


def test_build_zoominfo_client_success(monkeypatch):
    rc = _RecordingClient([_FakeResp(json_data={"access_token": "TKN"})])
    monkeypatch.setattr(enrich.httpx, "Client", lambda *a, **k: rc)
    client = enrich.build_zoominfo_client(_settings())
    assert isinstance(client, ZoomInfoClient)
    method, url, kw = rc.calls[0]
    assert method == "POST" and url.endswith("/oauth/v1/token")
    assert kw["data"]["grant_type"] == "client_credentials"
    assert kw["headers"]["Authorization"].startswith("Basic ")


def test_build_zoominfo_client_no_token_raises(monkeypatch):
    monkeypatch.setattr(enrich.httpx, "Client",
                        lambda *a, **k: _RecordingClient([_FakeResp(json_data={})]))
    with pytest.raises(enrich._FatalEnrichError):
        enrich.build_zoominfo_client(_settings())


def test_build_zoominfo_client_http_error_raises(monkeypatch):
    monkeypatch.setattr(enrich.httpx, "Client",
                        lambda *a, **k: _RecordingClient([_FakeResp(status_code=401)]))
    with pytest.raises(enrich._FatalEnrichError):
        enrich.build_zoominfo_client(_settings())


def test_upsert_contact_deletes_then_inserts(monkeypatch):
    rc = _RecordingClient([_FakeResp(), _FakeResp()])  # delete, insert
    monkeypatch.setattr(enrich.httpx, "Client", lambda *a, **k: rc)
    enrich._upsert_contact("c1", "CF Logistics LLC", 245000, 4200,
                           "https://sb.example.co", "k", 5.0)
    assert [c[0] for c in rc.calls] == ["DELETE", "POST"]  # idempotent: delete first
    insert_body = rc.calls[1][2]["json"]
    assert insert_body["creditor_id"] == "c1" and insert_body["full_name"] == "CF Logistics LLC"
    assert insert_body["company_revenue"] == 245000 and insert_body["company_employee_count"] == 4200
