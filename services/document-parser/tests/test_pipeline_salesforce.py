"""Unit tests for pipeline/salesforce.py — the salesforce_push stage (KD-68).

A fake duck-typed Salesforce client stands in for simple_salesforce; Supabase
reads/writes are monkeypatched via the module httpx idiom. No live org is hit.
"""

import httpx
import pytest
from pipeline.salesforce import (
    RECENCY_EXISTING,
    RECENCY_NEW,
    PushResult,
    SalesforcePusher,
    _chapter_label,
    _ManualReview,
    _soql_escape,
    _tier_label,
    _zoominfo_url,
)

from pipeline import salesforce

# ---------------------------------------------------------------------------
# Fake Salesforce client
# ---------------------------------------------------------------------------

class _FakeSFType:
    def __init__(self, name, parent):
        self._name = name
        self._p = parent

    def create(self, data):
        self._p.calls.append((self._name, "create", data))
        new_id = f"{self._name[:3].upper()}{len(self._p.calls):015d}"
        return {"id": new_id, "success": True}

    def update(self, rec_id, data):
        self._p.calls.append((self._name, "update", rec_id, data))
        return 204

    def upsert(self, ext_path, data):
        self._p.calls.append((self._name, "upsert", ext_path, data))
        return 200


class _FakeSF:
    """Serves canned query results (matched in insertion order by a predicate)."""

    def __init__(self, query_handler=None):
        self.calls = []
        self.queries = []
        self._qh = query_handler or (lambda q: {"totalSize": 0, "records": []})

    def query(self, soql):
        self.queries.append(soql)
        return self._qh(soql)

    def __getattr__(self, name):
        # Any *_c / standard object access returns a fake SFType.
        if name.startswith("_"):
            raise AttributeError(name)
        return _FakeSFType(name, self)


def _pusher(sf):
    return SalesforcePusher(sf, "https://sb.example.co", "svc-key", 5.0)


_BANKRUPTCY = {
    "case_number": "2:23-bk-13359", "debtor_name": "AeroFarms, Inc",
    "filing_date": "2023-06-08", "court_district": "District of New Jersey",
    "chapter_type": "11", "state": "NJ",
}


def _creditor(**over):
    base = {"creditor_id": "cred-1", "creditor_name": "Cf Logistics",
            "normalized_name": "CF LOGISTICS", "creditor_state": "NJ",
            "claim_amount": 110917, "creditor_address": "Newark, NJ"}
    base.update(over)
    return base


# Patch _persist_account_map (Supabase writes) to a recorder by default.
@pytest.fixture(autouse=True)
def _no_persist(monkeypatch):
    recorded = []
    monkeypatch.setattr(salesforce, "_persist_account_map",
                        lambda cid, aid, rec, *a: recorded.append((cid, aid, rec)))
    monkeypatch.setattr(salesforce, "_SF_RETRY_BASE_SEC", 0.0)
    return recorded


# ---------------------------------------------------------------------------
# Pure mappers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("11", "Chapter 11"), ("7", "Chapter 7"), ("11-Subchapter-V", "Chapter 11"),
    ("15", None), ("", None), (None, None),
])
def test_chapter_label(raw, expected):
    assert _chapter_label(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    (1, "Enterprise"), (2, "Mid-Market"), (3, "SMB"), ("2", "Mid-Market"),
    (0, None), (None, None), ("x", None),
])
def test_tier_label(raw, expected):
    assert _tier_label(raw) == expected


def test_zoominfo_url():
    assert _zoominfo_url("12345") == "https://app.zoominfo.com/#/company/12345/overview"
    assert _zoominfo_url("  ") == ""
    assert _zoominfo_url(None) == ""


def test_soql_escape():
    assert _soql_escape("Macy's") == r"Macy\'s"
    assert _soql_escape(None) == ""
    assert _soql_escape(r"a\b") == r"a\\b"


# ---------------------------------------------------------------------------
# Account match seam — 0 / 1 / many / state tiebreak / manual review
# ---------------------------------------------------------------------------

def test_find_account_no_match_returns_none():
    sf = _FakeSF(lambda q: {"totalSize": 0, "records": []})
    assert _pusher(sf)._find_account(_creditor()) is None


def test_find_account_single_match():
    sf = _FakeSF(lambda q: {"totalSize": 1, "records": [{"Id": "001AAA", "BillingState": "NJ"}]})
    assert _pusher(sf)._find_account(_creditor()) == "001AAA"


def test_find_account_ambiguous_resolved_by_state():
    def qh(q):
        return {"totalSize": 2, "records": [
            {"Id": "001NJ", "BillingState": "NJ"},
            {"Id": "001NY", "BillingState": "NY"}]}
    sf = _FakeSF(qh)
    assert _pusher(sf)._find_account(_creditor(creditor_state="NJ")) == "001NJ"


def test_find_account_ambiguous_unresolved_raises_manual_review():
    sf = _FakeSF(lambda q: {"totalSize": 2, "records": [
        {"Id": "001A", "BillingState": "NJ"}, {"Id": "001B", "BillingState": "NJ"}]})
    with pytest.raises(_ManualReview):
        _pusher(sf)._find_account(_creditor(creditor_state="NJ"))


def test_find_account_falls_back_to_raw_name():
    # normalized_name misses, raw creditor_name hits.
    def qh(q):
        if "CF LOGISTICS" in q:
            return {"totalSize": 0, "records": []}
        return {"totalSize": 1, "records": [{"Id": "001RAW", "BillingState": "NJ"}]}
    sf = _FakeSF(qh)
    assert _pusher(sf)._find_account(_creditor()) == "001RAW"


# ---------------------------------------------------------------------------
# match_or_create + field mapping
# ---------------------------------------------------------------------------

def test_match_or_create_creates_when_no_match():
    sf = _FakeSF(lambda q: {"totalSize": 0, "records": []})
    aid = _pusher(sf)._match_or_create_account(_creditor(), {"company_tier": 1, "zoominfo_company_id": "999"})
    creates = [c for c in sf.calls if c[0] == "Account" and c[1] == "create"]
    assert len(creates) == 1
    data = creates[0][2]
    assert data["Name"] == "CF LOGISTICS"
    assert data["Company_Tier__c"] == "Enterprise"
    assert data["ZoomInfo__c"] == "https://app.zoominfo.com/#/company/999/overview"
    assert data["BillingState"] == "NJ"
    assert aid.startswith("ACC")


def test_match_or_create_updates_when_matched():
    sf = _FakeSF(lambda q: {"totalSize": 1, "records": [{"Id": "001X", "BillingState": "NJ"}]})
    aid = _pusher(sf)._match_or_create_account(_creditor(), {"company_tier": 2, "zoominfo_company_id": None})
    assert aid == "001X"
    updates = [c for c in sf.calls if c[0] == "Account" and c[1] == "update"]
    assert updates and updates[0][3]["Company_Tier__c"] == "Mid-Market"
    assert "ZoomInfo__c" not in updates[0][3]  # no zoominfo id → not set


# ---------------------------------------------------------------------------
# Debtor upsert
# ---------------------------------------------------------------------------

def test_upsert_debtor_upserts_and_resolves_id():
    sf = _FakeSF(lambda q: {"totalSize": 1, "records": [{"Id": "a0B999"}]})
    bc_id = _pusher(sf)._upsert_debtor(_BANKRUPTCY)
    assert bc_id == "a0B999"
    ups = [c for c in sf.calls if c[0] == "Bankrupt_Companies__c" and c[1] == "upsert"]
    assert ups, "debtor should be upserted"
    ext_path, data = ups[0][2], ups[0][3]
    assert ext_path.startswith("Case_Number__c/")
    assert data["Chapter__c"] == "Chapter 11"
    assert data["Name"] == "AeroFarms, Inc"
    assert "PACER_URL__c" not in data and "Address__c" not in data  # not in DB


def test_upsert_debtor_raises_without_case_number():
    sf = _FakeSF()
    with pytest.raises(salesforce._FatalSalesforceError):
        _pusher(sf)._upsert_debtor({"debtor_name": "X"})


# ---------------------------------------------------------------------------
# Creditor row (Bankruptcy__c) dedup
# ---------------------------------------------------------------------------

def test_creditor_row_created_when_absent():
    sf = _FakeSF(lambda q: {"totalSize": 0, "records": []})
    _pusher(sf)._upsert_creditor_row("001ACC", "a0BC", _BANKRUPTCY, _creditor())
    creates = [c for c in sf.calls if c[0] == "Bankruptcy__c" and c[1] == "create"]
    assert len(creates) == 1
    data = creates[0][2]
    assert data["Account__c"] == "001ACC" and data["Bankrupt_Company__c"] == "a0BC"
    assert data["Amount__c"] == 110917 and data["Chapter__c"] == "Chapter 11"


def test_creditor_row_updated_when_present():
    sf = _FakeSF(lambda q: {"totalSize": 1, "records": [{"Id": "a0CR1"}]})
    _pusher(sf)._upsert_creditor_row("001ACC", "a0BC", _BANKRUPTCY, _creditor())
    assert [c for c in sf.calls if c[0] == "Bankruptcy__c" and c[1] == "update"]
    assert not [c for c in sf.calls if c[0] == "Bankruptcy__c" and c[1] == "create"]


# ---------------------------------------------------------------------------
# Recency
# ---------------------------------------------------------------------------

def test_recency_existing_on_open_opportunity():
    sf = _FakeSF(lambda q: {"totalSize": 1, "records": [{"Id": "o1"}]} if "Opportunity" in q
                 else {"totalSize": 0, "records": []})
    assert _pusher(sf)._compute_recency("001X") == RECENCY_EXISTING


def test_recency_existing_on_recent_task():
    sf = _FakeSF(lambda q: {"totalSize": 1, "records": [{"Id": "t1"}]} if "FROM Task" in q
                 else {"totalSize": 0, "records": []})
    assert _pusher(sf)._compute_recency("001X") == RECENCY_EXISTING


def test_recency_new_when_no_activity():
    sf = _FakeSF(lambda q: {"totalSize": 0, "records": []})
    assert _pusher(sf)._compute_recency("001X") == RECENCY_NEW


# ---------------------------------------------------------------------------
# push_bankruptcy — happy path, persistence ordering, isolation
# ---------------------------------------------------------------------------

def test_push_bankruptcy_happy_path(_no_persist):
    # debtor Id lookup, then per creditor: account match (none→create), row (none→create), recency (none)
    def qh(q):
        if "Bankrupt_Companies__c" in q:
            return {"totalSize": 1, "records": [{"Id": "a0BC"}]}
        return {"totalSize": 0, "records": []}
    sf = _FakeSF(qh)
    res = _pusher(sf).push_bankruptcy(_BANKRUPTCY, [_creditor()], {"cred-1": {"company_tier": 3}})
    assert res.pushed == 1 and not res.failed and not res.manual_review
    # persisted: creditor_id, some account id, recency NEW
    assert _no_persist and _no_persist[0][0] == "cred-1" and _no_persist[0][2] == RECENCY_NEW


def test_push_bankruptcy_isolates_failures(_no_persist):
    # One creditor's account lookup fails (after retries); the other still pushes.
    def qh(q):
        if "Bankrupt_Companies__c" in q:
            return {"totalSize": 1, "records": [{"Id": "a0BC"}]}
        if "FAILCO" in q:  # cred-2's distinctive name → unrecoverable transient
            raise httpx.ConnectError("boom")
        return {"totalSize": 0, "records": []}
    sf = _FakeSF(qh)
    res = _pusher(sf).push_bankruptcy(
        _BANKRUPTCY,
        [_creditor(creditor_id="cred-1"),
         _creditor(creditor_id="cred-2", normalized_name="FAILCO", creditor_name="FailCo")],
        {})
    assert res.pushed == 1
    assert res.failed == ["cred-2"]


def test_push_bankruptcy_manual_review_counted(_no_persist):
    def qh(q):
        if "Bankrupt_Companies__c" in q:
            return {"totalSize": 1, "records": [{"Id": "a0BC"}]}
        if "FROM Account" in q:
            return {"totalSize": 2, "records": [{"Id": "a", "BillingState": "NJ"},
                                                {"Id": "b", "BillingState": "NJ"}]}
        return {"totalSize": 0, "records": []}
    sf = _FakeSF(qh)
    res = _pusher(sf).push_bankruptcy(_BANKRUPTCY, [_creditor()], {})
    assert res.manual_review == ["cred-1"] and res.pushed == 0


# ---------------------------------------------------------------------------
# process_job orchestration + guard
# ---------------------------------------------------------------------------

def _settings(**over):
    from types import SimpleNamespace
    base = dict(supabase_url="https://sb.example.co", supabase_service_role_key="k",
                supabase_http_timeout_sec=5.0, salesforce_username="u",
                salesforce_password="p", salesforce_security_token="t",
                salesforce_domain="login")
    base.update(over)
    return SimpleNamespace(**base)


def test_process_job_guard_missing_creds(monkeypatch):
    monkeypatch.setattr(salesforce, "get_pipeline_settings",
                        lambda: _settings(salesforce_username="", salesforce_password=""))
    with pytest.raises(salesforce._FatalSalesforceError):
        salesforce.process_job({"id": "j1", "bankruptcy_id": "b1"})


def test_process_job_no_bankruptcy_id(monkeypatch):
    monkeypatch.setattr(salesforce, "get_pipeline_settings", lambda: _settings())
    with pytest.raises(salesforce._FatalSalesforceError):
        salesforce.process_job({"id": "j1"})


def test_process_job_no_creditors_completes(monkeypatch):
    monkeypatch.setattr(salesforce, "get_pipeline_settings", lambda: _settings())
    monkeypatch.setattr(salesforce, "_get_bankruptcy", lambda *a: dict(_BANKRUPTCY))
    monkeypatch.setattr(salesforce, "_list_company_creditors", lambda *a: [])
    built = {"sf": False}
    monkeypatch.setattr(salesforce, "_build_sf_client", lambda s: built.__setitem__("sf", True))
    salesforce.process_job({"id": "j1", "bankruptcy_id": "b1"})  # returns (completes)
    assert built["sf"] is False  # short-circuits before building the SF client


def test_process_job_full(monkeypatch):
    monkeypatch.setattr(salesforce, "get_pipeline_settings", lambda: _settings())
    monkeypatch.setattr(salesforce, "_get_bankruptcy", lambda *a: dict(_BANKRUPTCY))
    monkeypatch.setattr(salesforce, "_list_company_creditors", lambda *a: [_creditor()])
    monkeypatch.setattr(salesforce, "_get_enrichment", lambda *a: {"cred-1": {"company_tier": 1}})
    monkeypatch.setattr(salesforce, "_persist_account_map", lambda *a: None)

    def qh(q):
        if "Bankrupt_Companies__c" in q:
            return {"totalSize": 1, "records": [{"Id": "a0BC"}]}
        return {"totalSize": 0, "records": []}
    monkeypatch.setattr(salesforce, "_build_sf_client", lambda s: _FakeSF(qh))
    salesforce.process_job({"id": "j1", "bankruptcy_id": "b1"})  # no raise = completed


def test_process_job_all_failed_raises(monkeypatch):
    monkeypatch.setattr(salesforce, "get_pipeline_settings", lambda: _settings())
    monkeypatch.setattr(salesforce, "_get_bankruptcy", lambda *a: dict(_BANKRUPTCY))
    monkeypatch.setattr(salesforce, "_list_company_creditors", lambda *a: [_creditor()])
    monkeypatch.setattr(salesforce, "_get_enrichment", lambda *a: {})
    monkeypatch.setattr(salesforce, "_SF_RETRY_BASE_SEC", 0.0)

    def qh(q):
        if "Bankrupt_Companies__c" in q:
            return {"totalSize": 1, "records": [{"Id": "a0BC"}]}
        raise httpx.ConnectError("down")  # every account lookup fails
    monkeypatch.setattr(salesforce, "_build_sf_client", lambda s: _FakeSF(qh))
    with pytest.raises(RuntimeError):
        salesforce.process_job({"id": "j1", "bankruptcy_id": "b1"})
