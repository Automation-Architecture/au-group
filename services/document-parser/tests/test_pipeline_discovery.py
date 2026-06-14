"""Unit tests for pipeline/discovery.py — CourtListener Chapter 11 discovery (OD-8).

Mocks the CourtListener Search API via the module httpx idiom. No live calls.
discover() returns (cases, complete); complete=False means the window was not
fully enumerated and the caller must not advance its watermark.
"""
from datetime import date

import httpx
import pytest
from pipeline.discovery import CourtListenerDiscoverer, DiscoveredCase

from pipeline import discovery


class _FakeResp:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            req = httpx.Request("GET", "http://x")
            raise httpx.HTTPStatusError("e", request=req,
                                        response=httpx.Response(self.status_code, request=req))


class _FakeClient:
    def __init__(self, queue):
        self._q = queue
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url, **k):
        self.calls.append({"url": url, "params": k.get("params")})
        item = self._q.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _patch(monkeypatch, queue):
    fake = _FakeClient(queue)
    monkeypatch.setattr(discovery.httpx, "Client", lambda *a, **k: fake)
    monkeypatch.setattr(discovery, "_DISCOVERY_RETRY_BASE_SEC", 0.0)
    return fake


def _result(docket="26-16653", name="ACME LLC", court="njb", filed="2026-06-09", chapter="11"):
    return {"docket_id": 1, "docketNumber": docket, "caseName": name,
            "court_id": court, "dateFiled": filed, "chapter": chapter,
            "docket_absolute_url": "/docket/1/acme/"}


_FROM = date(2026, 6, 1)
_TO = date(2026, 6, 14)


def _disc(**kw):
    return CourtListenerDiscoverer("tok", timeout=5.0, **kw)


def test_discover_parses_and_maps_fields(monkeypatch):
    _patch(monkeypatch, [_FakeResp(json_data={"results": [_result()], "next": None})])
    cases, complete = _disc().discover(["njb"], _FROM, _TO)
    assert complete is True and len(cases) == 1
    c = cases[0]
    assert isinstance(c, DiscoveredCase)
    assert c.court_id == "njb" and c.case_number_full == "26-16653"
    assert c.case_title == "ACME LLC" and c.date_filed == "2026-06-09" and c.chapter == "11"


def test_discover_query_params(monkeypatch):
    fake = _patch(monkeypatch, [_FakeResp(json_data={"results": [], "next": None})])
    _disc().discover(["njb", "nysb"], _FROM, _TO, chapter=11)
    p = fake.calls[0]["params"]
    assert p["type"] == "r" and p["court"] == "njb nysb" and p["q"] == "chapter:11"
    assert p["filed_after"] == "2026-06-01" and p["filed_before"] == "2026-06-14"
    assert p["order_by"] == "dateFiled desc"


def test_discover_drops_future_and_blank_and_no_docket(monkeypatch):
    rows = [_result(docket="26-1", filed="2026-06-10"),
            _result(docket="99-9", filed="2029-01-01"),     # future sentinel
            _result(docket="26-7", filed=""),               # blank date → skip
            {"caseName": "no docket", "dateFiled": "2026-06-10"}]  # missing docketNumber
    _patch(monkeypatch, [_FakeResp(json_data={"results": rows, "next": None})])
    cases, complete = _disc().discover(["njb"], _FROM, _TO)
    assert complete is True
    assert [c.case_number_full for c in cases] == ["26-1"]


def test_discover_paginates_via_next(monkeypatch):
    page1 = _FakeResp(json_data={"results": [_result(docket="26-1")],
                                 "next": "https://www.courtlistener.com/api/rest/v4/search/?cursor=A"})
    page2 = _FakeResp(json_data={"results": [_result(docket="26-2")], "next": None})
    _patch(monkeypatch, [page1, page2])
    cases, complete = _disc().discover(["njb"], _FROM, _TO)
    assert complete is True
    assert sorted(c.case_number_full for c in cases) == ["26-1", "26-2"]


def test_discover_page_cap_marks_incomplete(monkeypatch):
    def page(dn):
        return _FakeResp(json_data={"results": [_result(docket=dn)], "next": "https://x/?cursor=Z"})

    _patch(monkeypatch, [page("26-1"), page("26-2"), page("26-3")])
    cases, complete = _disc(max_pages=2).discover(["njb"], _FROM, _TO)
    assert len(cases) == 2 and complete is False  # cap hit with cursor pending → incomplete


def test_discover_midpagination_failure_marks_incomplete(monkeypatch):
    page1 = _FakeResp(json_data={"results": [_result(docket="26-1")], "next": "https://x/?cursor=Z"})
    # page 2 fetch fails on every retry → incomplete, partial result
    _patch(monkeypatch, [page1] + [httpx.ConnectError("down")] * 4)
    cases, complete = _disc().discover(["njb"], _FROM, _TO)
    assert [c.case_number_full for c in cases] == ["26-1"] and complete is False


def test_discover_retries_on_429(monkeypatch):
    _patch(monkeypatch, [_FakeResp(status_code=429),
                         _FakeResp(json_data={"results": [_result()], "next": None})])
    cases, complete = _disc().discover(["njb"], _FROM, _TO)
    assert len(cases) == 1 and complete is True


def test_discover_empty_courts_complete_no_call(monkeypatch):
    fake = _patch(monkeypatch, [])
    assert _disc().discover([], _FROM, _TO) == ([], True)
    assert fake.calls == []


def test_discover_total_failure_incomplete(monkeypatch):
    _patch(monkeypatch, [httpx.ConnectError("down")] * 4)
    cases, complete = _disc().discover(["njb"], _FROM, _TO)
    assert cases == [] and complete is False  # outage must NOT look like an empty window
