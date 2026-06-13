"""Unit tests for pipeline/retrieval.py — pluggable Form 204 retrieval.

The RECAP adapter is built against the documented CourtListener v4 contract
(docs/architecture/courtlistener-recap-api-reference.md); these tests mock the
documented response shapes. No live API token is exercised here.
"""

import httpx
import pytest
from pipeline.retrieval import (
    CaseRef,
    CompositeRetriever,
    PacerCmecfRetriever,
    RecapRetriever,
    RetrievalResult,
    _pick_form_204,
    recap_docket_number,
)

from pipeline import retrieval

# ---------------------------------------------------------------------------
# Fakes (mirrors the httpx.Client monkeypatch idiom used across pipeline tests)
# ---------------------------------------------------------------------------

class _FakeResp:
    def __init__(self, status_code=200, json_data=None, content=b"", headers=None):
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.content = content
        self.headers = headers or {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            req = httpx.Request("GET", "http://x")
            raise httpx.HTTPStatusError(
                "err", request=req, response=httpx.Response(self.status_code, request=req)
            )


class _FakeClient:
    """Context-manager httpx.Client stand-in serving queued responses in order."""

    def __init__(self, queue):
        self._queue = queue

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, *a, **k):
        item = self._queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _patch(monkeypatch, queue):
    monkeypatch.setattr(retrieval.httpx, "Client", lambda *a, **k: _FakeClient(queue))


def _pdf(headers=None):
    return _FakeResp(content=b"%PDF-1.4 fake", headers=headers or {"content-type": "application/pdf"})


# A search result with one nested recap-document that IS the Form 204.
def _search_hit():
    return _FakeResp(json_data={"results": [{
        "docket_id": 42, "caseName": "ACME Corp", "docketNumber": "23-13359",
        "recap_documents": [{
            "description": "Chapter 11 Voluntary Petition", "short_description": "Petition",
            "document_number": "1", "page_count": 50, "is_available": True,
            "filepath_local": "recap/x/petition.pdf",
        }, {
            "description": "List of Creditors Who Have the 20 Largest Unsecured Claims",
            "short_description": "20 Largest Unsecured", "document_number": "2",
            "page_count": 3, "is_available": True, "filepath_local": "recap/x/form204.pdf",
        }],
    }]})


# ---------------------------------------------------------------------------
# recap_docket_number
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("2:23-bk-13359", "23-13359"),
    ("1:26bk12345", "26-12345"),
    ("23-bk-00045", "23-00045"),
    ("23-13359", "23-13359"),
    ("nonsense", "nonsense"),
    ("", ""),
])
def test_recap_docket_number(raw, expected):
    assert recap_docket_number(raw) == expected


# ---------------------------------------------------------------------------
# _pick_form_204 — identification + availability + sorting
# ---------------------------------------------------------------------------

def test_pick_prefers_matching_available_doc():
    docs = [
        {"description": "Voluntary Petition", "document_number": "1", "page_count": 40,
         "is_available": True, "filepath_local": "a.pdf"},
        {"description": "20 Largest Unsecured Claims", "document_number": "2", "page_count": 3,
         "is_available": True, "filepath_local": "b.pdf"},
    ]
    assert _pick_form_204(docs)["filepath_local"] == "b.pdf"


def test_pick_accepts_consolidated_top_30():
    docs = [{"description": "Consolidated List of Creditors Who Have the 30 Largest Unsecured Claims",
             "document_number": "5", "page_count": 4, "is_available": True, "filepath_local": "c.pdf"}]
    assert _pick_form_204(docs)["filepath_local"] == "c.pdf"


def test_pick_skips_unavailable_doc():
    docs = [{"description": "20 Largest Unsecured", "document_number": "2", "page_count": 3,
             "is_available": False, "filepath_local": "b.pdf"}]
    assert _pick_form_204(docs) is None


def test_pick_skips_doc_without_filepath():
    docs = [{"description": "20 Largest Unsecured", "document_number": "2", "page_count": 3,
             "is_available": True, "filepath_local": ""}]
    assert _pick_form_204(docs) is None


def test_pick_ignores_non_matching_descriptions():
    docs = [{"description": "Notice of Agenda", "document_number": "9", "page_count": 1,
             "is_available": True, "filepath_local": "z.pdf"}]
    assert _pick_form_204(docs) is None


def test_pick_tiebreaks_lowest_document_then_pages():
    docs = [
        {"description": "Largest Unsecured", "document_number": "8", "page_count": 2,
         "is_available": True, "filepath_local": "late.pdf"},
        {"description": "Largest Unsecured", "document_number": "2", "page_count": 30,
         "is_available": True, "filepath_local": "early.pdf"},
    ]
    assert _pick_form_204(docs)["filepath_local"] == "early.pdf"


# ---------------------------------------------------------------------------
# RecapRetriever — happy path via Search, then download
# ---------------------------------------------------------------------------

def _case():
    return CaseRef(court_id="njb", case_number_full="2:23-bk-13359", debtor_name="ACME Corp")


def test_recap_retrieve_via_search(monkeypatch):
    _patch(monkeypatch, [_search_hit(), _pdf()])
    res = RecapRetriever("tok").retrieve(_case())
    assert isinstance(res, RetrievalResult)
    assert res.source == "recap"
    assert res.pdf.startswith(b"%PDF")
    assert res.document_number == "2"
    assert res.page_count == 3
    assert "free" in res.cost_note.lower()


def test_recap_falls_back_to_docket_entries(monkeypatch):
    # search returns no nested match → dockets lookup → docket-entries → download
    search_empty = _FakeResp(json_data={"results": [{"recap_documents": []}]})
    dockets = _FakeResp(json_data={"results": [{"id": 99, "case_name": "ACME Corp"}]})
    entries = _FakeResp(json_data={"results": [
        {"recap_documents": [{"description": "Voluntary Petition", "document_number": "1",
                              "page_count": 60, "is_available": True, "filepath_local": "p.pdf"}]},
        {"recap_documents": [{"description": "List of Creditors Holding 20 Largest Unsecured Claims",
                              "document_number": "3", "page_count": 2, "is_available": True,
                              "filepath_local": "f204.pdf"}]},
    ], "next": None})
    _patch(monkeypatch, [search_empty, dockets, entries, _pdf()])
    res = RecapRetriever("tok").retrieve(_case())
    assert res is not None
    assert res.source == "recap"
    assert res.document_number == "3"


def test_recap_returns_none_when_not_archived(monkeypatch):
    # search empty, docket found, entries have only a non-matching doc → miss
    search_empty = _FakeResp(json_data={"results": []})
    dockets = _FakeResp(json_data={"results": [{"id": 99}]})
    entries = _FakeResp(json_data={"results": [
        {"recap_documents": [{"description": "Notice", "document_number": "4", "is_available": True,
                              "filepath_local": "n.pdf"}]}], "next": None})
    _patch(monkeypatch, [search_empty, dockets, entries])
    assert RecapRetriever("tok").retrieve(_case()) is None


def test_recap_returns_none_when_no_docket_found(monkeypatch):
    search_empty = _FakeResp(json_data={"results": []})
    dockets_empty = _FakeResp(json_data={"results": []})
    _patch(monkeypatch, [search_empty, dockets_empty])
    assert RecapRetriever("tok").retrieve(_case()) is None


def test_recap_rejects_non_pdf_download(monkeypatch):
    html = _FakeResp(content=b"<html>", headers={"content-type": "text/html"})
    _patch(monkeypatch, [_search_hit(), html])
    assert RecapRetriever("tok").retrieve(_case()) is None


def test_recap_search_http_error_falls_through_to_walk(monkeypatch):
    # search raises → walk: dockets + entries succeed
    err = httpx.ConnectError("boom")
    dockets = _FakeResp(json_data={"results": [{"id": 7}]})
    entries = _FakeResp(json_data={"results": [
        {"recap_documents": [{"description": "20 Largest Unsecured", "document_number": "2",
                              "page_count": 3, "is_available": True, "filepath_local": "f.pdf"}]}],
        "next": None})
    _patch(monkeypatch, [err, dockets, entries, _pdf()])
    res = RecapRetriever("tok").retrieve(_case())
    assert res is not None and res.source == "recap"


def test_recap_entries_pagination_capped(monkeypatch):
    # 3 entry pages each with a 'next' and no match → stops at max_entry_pages, returns None
    search_empty = _FakeResp(json_data={"results": []})
    dockets = _FakeResp(json_data={"results": [{"id": 1}]})

    def page():
        return _FakeResp(json_data={"results": [
            {"recap_documents": [{"description": "Order", "is_available": True, "filepath_local": "o.pdf"}]}],
            "next": "https://www.courtlistener.com/api/rest/v4/docket-entries/?page=2"})

    _patch(monkeypatch, [search_empty, dockets, page(), page(), page()])
    assert RecapRetriever("tok", max_entry_pages=3).retrieve(_case()) is None


# ---------------------------------------------------------------------------
# PacerCmecfRetriever
# ---------------------------------------------------------------------------

class _FakePacer:
    def __init__(self, pdf):
        self._pdf = pdf
        self.calls = []

    def download_form_204(self, case_link, token):
        self.calls.append((case_link, token))
        return self._pdf


def test_pacer_retriever_success():
    pacer = _FakePacer(b"%PDF-data")
    case = CaseRef(court_id="njb", case_number_full="23-1", debtor_name="X", case_link="http://ecf/1")
    res = PacerCmecfRetriever(pacer, "tok").retrieve(case)
    assert res.source == "pacer_cmecf"
    assert res.pdf == b"%PDF-data"
    assert pacer.calls == [("http://ecf/1", "tok")]


def test_pacer_retriever_none_when_not_found():
    res = PacerCmecfRetriever(_FakePacer(None), "tok").retrieve(
        CaseRef(court_id="njb", case_number_full="23-1", debtor_name="X", case_link="http://ecf/1"))
    assert res is None


def test_pacer_retriever_skips_when_no_case_link():
    pacer = _FakePacer(b"%PDF")
    res = PacerCmecfRetriever(pacer, "tok").retrieve(
        CaseRef(court_id="njb", case_number_full="23-1", debtor_name="X", case_link=""))
    assert res is None
    assert pacer.calls == []  # never even attempted


# ---------------------------------------------------------------------------
# CompositeRetriever — cheapest-first ordering + fault isolation
# ---------------------------------------------------------------------------

class _Stub:
    def __init__(self, result=None, raises=None):
        self._result = result
        self._raises = raises
        self.called = False

    def retrieve(self, case):
        self.called = True
        if self._raises:
            raise self._raises
        return self._result


def _ref():
    return CaseRef(court_id="njb", case_number_full="23-1", debtor_name="X")


def test_composite_returns_first_hit_and_skips_rest():
    hit = RetrievalResult(pdf=b"%PDF", source="recap")
    first, second = _Stub(result=hit), _Stub(result=RetrievalResult(pdf=b"x", source="pacer_cmecf"))
    res = CompositeRetriever([first, second]).retrieve(_ref())
    assert res.source == "recap"
    assert first.called and not second.called


def test_composite_falls_through_on_miss():
    miss = _Stub(result=None)
    hit = _Stub(result=RetrievalResult(pdf=b"%PDF", source="pacer_cmecf"))
    res = CompositeRetriever([miss, hit]).retrieve(_ref())
    assert res.source == "pacer_cmecf"
    assert miss.called and hit.called


def test_composite_isolates_a_raising_retriever():
    boom = _Stub(raises=RuntimeError("kaboom"))
    hit = _Stub(result=RetrievalResult(pdf=b"%PDF", source="pacer_cmecf"))
    res = CompositeRetriever([boom, hit]).retrieve(_ref())
    assert res is not None and res.source == "pacer_cmecf"


def test_composite_all_miss_returns_none():
    assert CompositeRetriever([_Stub(result=None), _Stub(result=None)]).retrieve(_ref()) is None


# ---------------------------------------------------------------------------
# Identification: reject the matrix and docs that merely reference the list
# ---------------------------------------------------------------------------

def test_pick_rejects_full_creditor_matrix():
    # The bare creditor matrix / mailing list has no "largest" → not a Form 204.
    docs = [
        {"description": "List of Creditors", "document_number": "2", "page_count": 200,
         "is_available": True, "filepath_local": "matrix.pdf"},
        {"description": "Creditor Matrix", "document_number": "3", "page_count": 150,
         "is_available": True, "filepath_local": "m2.pdf"},
    ]
    assert _pick_form_204(docs) is None


def test_pick_rejects_order_referencing_the_list():
    # An order/motion that cites "30 Largest" is not the list itself.
    docs = [{"description": "Interim Order Authorizing the Debtors to File a "
                            "Consolidated List of the 30 Largest Unsecured Creditors",
             "document_number": "1", "page_count": 5, "is_available": True,
             "filepath_local": "order.pdf"}]
    assert _pick_form_204(docs) is None


# ---------------------------------------------------------------------------
# RecapRetriever: docket-id reuse, name disambiguation, robust I/O
# ---------------------------------------------------------------------------

def test_recap_reuses_docket_id_from_search(monkeypatch):
    # Search returns the docket_id but no matching doc in the slice → the walk
    # must reuse the id and NOT re-query /dockets/. Queue: search, entries, pdf.
    search = _FakeResp(json_data={"results": [{"docket_id": 555, "recap_documents": [
        {"description": "Voluntary Petition", "document_number": "1", "is_available": True,
         "filepath_local": "p.pdf"}]}]})
    entries = _FakeResp(json_data={"results": [
        {"recap_documents": [{"description": "20 Largest Unsecured", "document_number": "2",
                              "page_count": 3, "is_available": True, "filepath_local": "f.pdf"}]}],
        "next": None})
    _patch(monkeypatch, [search, entries, _pdf()])
    res = RecapRetriever("tok").retrieve(_case())
    assert res is not None and res.document_number == "2"


def test_find_docket_id_disambiguates_by_name(monkeypatch):
    dockets = _FakeResp(json_data={"results": [
        {"id": 1, "case_name": "Other Debtor LLC"},
        {"id": 2, "case_name": "ACME Corp"}]})
    _patch(monkeypatch, [dockets])
    assert RecapRetriever("tok")._find_docket_id(_case()) == 2


def test_find_docket_id_falls_back_to_first_when_no_name_match(monkeypatch):
    dockets = _FakeResp(json_data={"results": [{"id": 7, "case_name": "Zzz Inc"}, {"id": 8}]})
    _patch(monkeypatch, [dockets])
    assert RecapRetriever("tok")._find_docket_id(_case()) == 7


def test_recap_rejects_empty_pdf_body(monkeypatch):
    empty = _FakeResp(content=b"", headers={"content-type": "application/pdf"})
    _patch(monkeypatch, [_search_hit(), empty])
    assert RecapRetriever("tok").retrieve(_case()) is None


def test_recap_non_json_search_falls_through_to_walk(monkeypatch):
    # A 200 with a non-JSON body must not abort the strategy or escalate to a
    # paid fetch — it returns None and the free docket-entries walk still runs.
    class _BadJson(_FakeResp):
        def json(self):
            raise ValueError("not json")

    dockets = _FakeResp(json_data={"results": [{"id": 3}]})
    entries = _FakeResp(json_data={"results": [
        {"recap_documents": [{"description": "20 Largest Unsecured", "document_number": "2",
                              "page_count": 3, "is_available": True, "filepath_local": "f.pdf"}]}],
        "next": None})
    _patch(monkeypatch, [_BadJson(), dockets, entries, _pdf()])
    res = RecapRetriever("tok").retrieve(_case())
    assert res is not None and res.source == "recap"
