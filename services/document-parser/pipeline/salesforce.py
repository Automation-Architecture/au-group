"""Pipeline Salesforce push stage — WP-09 (KD-68).

The worker dispatches ``salesforce_push`` jobs here (gated by ``SKIP_SF``; the
worker requeues while that flag is set).  For each job — one per bankruptcy —
this stage pushes every enriched **company** creditor into the client's live
Salesforce org, against the org's CONFIRMED existing schema (see
``docs/project/salesforce-audit.md`` §1c — do NOT create ``Bankruptcy_Event__c``):

  1. Upsert the debtor as ``Bankrupt_Companies__c`` on the ``Case_Number__c``
     external id (Name / Chapter__c / File_Date__c / Court_District__c).
  2. Match-or-create the creditor ``Account`` (FR-5.1 dedup against the client's
     existing ~13.5k accounts), set ``Company_Tier__c`` + ``ZoomInfo__c``.
  3. Create the creditor row as ``Bankruptcy__c`` (the "Creditors" related list:
     Account__c + Bankrupt_Company__c + Amount__c) — dedup query-then-write.
  4. Compute the FR-5.5 recency flag and persist it (RPC then PATCH).

Auth is username + password + security token (no Connected App yet — MVP).

Account match (the FR-5.1 crux) is intentionally isolated in ``_find_account``
so the strategy can be swapped once measured against the live org with real
creditor data.  Current strategy: exact Name match (SF Name match is
case-insensitive), disambiguated by BillingState only when Name is ambiguous —
so it does not depend on BillingState being populated (it is sparse on many
orgs).  0 matches → create (a new lead); 1 → reuse; >1 unresolved → flag manual
review and skip (never guess which account, EC-3.1).

NOTE (verification status): exercised by unit tests with an injected fake
Salesforce client; the live-org integration test (AC) is gated on real creditor
data flowing through intake/parse/enrich.  The exact-vs-fuzzy match decision
should be re-measured against the live org once such data exists.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import httpx

from pipeline.settings import PipelineSettings, get_pipeline_settings

logger = logging.getLogger(__name__)

# bankruptcies.chapter_type enum → Salesforce Chapter__c restricted picklist.
# SF has no Subchapter-V value; Subchapter V is a form of Chapter 11.
_CHAPTER_MAP = {"11": "Chapter 11", "7": "Chapter 7", "11-Subchapter-V": "Chapter 11"}
# creditors.company_tier smallint → Account.Company_Tier__c picklist.
_TIER_MAP = {1: "Enterprise", 2: "Mid-Market", 3: "SMB"}

RECENCY_EXISTING = "Existing activity in Salesforce"
RECENCY_NEW = "New Salesforce account"

# Transient-retry policy for Salesforce 503/5xx (per-call; module-level so tests
# can zero the delay).
_SF_MAX_ATTEMPTS = 3
_SF_RETRY_BASE_SEC = 1.0


class _FatalSalesforceError(RuntimeError):
    """Non-retryable push failure (missing creds/data) — worker fails + alerts."""


class _ManualReview(Exception):
    """A creditor needs human disambiguation (ambiguous Account match)."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _soql_escape(value: str | None) -> str:
    """Escape a string for safe interpolation inside a single-quoted SOQL literal."""
    return (value or "").replace("\\", "\\\\").replace("'", r"\'")


def _zoominfo_url(company_id: str | None) -> str:
    """Mirror au_group_zoominfo_company_url: build the ZoomInfo profile URL."""
    cid = (company_id or "").strip()
    return f"https://app.zoominfo.com/#/company/{cid}/overview" if cid else ""


def _chapter_label(chapter_type: str | None) -> str | None:
    return _CHAPTER_MAP.get((chapter_type or "").strip())


def _tier_label(company_tier: Any) -> str | None:
    try:
        return _TIER_MAP.get(int(company_tier))
    except (TypeError, ValueError):
        return None


def _is_sf_transient(exc: Exception) -> bool:
    """503/5xx/429 from Salesforce (or a network error) is worth retrying."""
    status = getattr(exc, "status", None)
    if isinstance(status, int):
        return status == 429 or 500 <= status < 600
    return isinstance(exc, httpx.RequestError)


def _sf_retry(fn, *args, **kwargs):
    """Call fn with exponential backoff on transient Salesforce errors."""
    last: Exception | None = None
    for attempt in range(1, _SF_MAX_ATTEMPTS + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — classify transient vs fatal
            last = exc
            if not _is_sf_transient(exc) or attempt == _SF_MAX_ATTEMPTS:
                raise
            delay = _SF_RETRY_BASE_SEC * (2 ** (attempt - 1))
            logger.warning("Salesforce call transient error (attempt %d/%d): %s — retrying in %.0fs",
                           attempt, _SF_MAX_ATTEMPTS, exc, delay)
            time.sleep(delay)
    raise last  # unreachable (loop re-raises) — for type-checkers


# ---------------------------------------------------------------------------
# Supabase reads / writes (httpx — same idiom as parse.py)
# ---------------------------------------------------------------------------

def _supabase_headers(key: str) -> dict[str, str]:
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _get_bankruptcy(bankruptcy_id: str, url: str, key: str, t: float) -> dict[str, Any] | None:
    with httpx.Client(timeout=t) as client:
        resp = client.get(
            f"{url.rstrip('/')}/rest/v1/bankruptcies",
            headers=_supabase_headers(key),
            params={"select": "case_number,debtor_name,filing_date,court_district,chapter_type,state",
                    "id": f"eq.{bankruptcy_id}", "limit": "1"},
        )
        resp.raise_for_status()
    rows = resp.json()
    return rows[0] if isinstance(rows, list) and rows else None


def _list_company_creditors(bankruptcy_id: str, url: str, key: str, t: float) -> list[dict[str, Any]]:
    """Company creditors for this filing (RPC — name/state/claim/normalized_name)."""
    with httpx.Client(timeout=t) as client:
        resp = client.post(
            f"{url.rstrip('/')}/rest/v1/rpc/au_group_list_company_creditors",
            headers=_supabase_headers(key),
            json={"p_bankruptcy_id": bankruptcy_id},
        )
        resp.raise_for_status()
    rows = resp.json()
    return rows if isinstance(rows, list) else []


def _get_enrichment(creditor_ids: list[str], url: str, key: str, t: float) -> dict[str, dict[str, Any]]:
    """Map creditor_id → {company_tier, zoominfo_company_id} (NULL until enrich runs)."""
    if not creditor_ids:
        return {}
    id_list = ",".join(creditor_ids)
    with httpx.Client(timeout=t) as client:
        resp = client.get(
            f"{url.rstrip('/')}/rest/v1/creditors",
            headers=_supabase_headers(key),
            params={"select": "id,company_tier,zoominfo_company_id", "id": f"in.({id_list})"},
        )
        resp.raise_for_status()
    return {r["id"]: r for r in resp.json()}


def _persist_account_map(creditor_id: str, sf_account_id: str, recency: str,
                         url: str, key: str, t: float) -> None:
    """Map creditor → SF account (RPC creates the row), then PATCH the recency flag.

    Order matters: the RPC upserts the salesforce_accounts row; the PATCH then
    sets sf_recency_status on that same row (the RPC does not touch it).
    """
    with httpx.Client(timeout=t) as client:
        resp = client.post(
            f"{url.rstrip('/')}/rest/v1/rpc/au_group_upsert_salesforce_account",
            headers=_supabase_headers(key),
            json={"p_creditor_id": creditor_id, "p_salesforce_account_id": sf_account_id},
        )
        resp.raise_for_status()
        patch = client.patch(
            f"{url.rstrip('/')}/rest/v1/salesforce_accounts",
            headers={**_supabase_headers(key), "Prefer": "return=minimal"},
            params={"creditor_id": f"eq.{creditor_id}"},
            json={"sf_recency_status": recency},
        )
        patch.raise_for_status()


# ---------------------------------------------------------------------------
# Push result
# ---------------------------------------------------------------------------

@dataclass
class PushResult:
    pushed: int = 0
    manual_review: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# The pusher (takes a duck-typed simple-salesforce client — injected for tests)
# ---------------------------------------------------------------------------

class SalesforcePusher:
    """Pushes one filing's creditors into Salesforce via an injected ``sf`` client.

    ``sf`` must quack like simple_salesforce.Salesforce: ``sf.query(soql)`` and
    per-object accessors (``sf.Account``, ``getattr(sf, 'Bankruptcy__c')`` …)
    with ``.create(dict)`` / ``.update(id, dict)`` / ``.upsert(ext_path, dict)``.
    """

    def __init__(self, sf: Any, supabase_url: str, supabase_key: str, timeout: float) -> None:
        self._sf = sf
        self._url = supabase_url
        self._key = supabase_key
        self._t = timeout

    # -- debtor ---------------------------------------------------------------
    def _upsert_debtor(self, b: dict[str, Any]) -> str:
        case_number = b.get("case_number")
        if not case_number:
            raise _FatalSalesforceError("bankruptcy row has no case_number")
        fields: dict[str, Any] = {"Name": (b.get("debtor_name") or "")[:80]}
        if b.get("filing_date"):
            fields["File_Date__c"] = b["filing_date"]
        if b.get("court_district"):
            fields["Court_District__c"] = b["court_district"]
        chapter = _chapter_label(b.get("chapter_type"))
        if chapter:
            fields["Chapter__c"] = chapter
        # Address__c / PACER_URL__c are not captured in the pipeline DB yet — omitted.

        obj = getattr(self._sf, "Bankrupt_Companies__c")
        _sf_retry(obj.upsert, f"Case_Number__c/{quote(str(case_number), safe='')}", fields)
        # upsert returns no id; resolve it by the external id we just keyed on.
        soql = f"SELECT Id FROM Bankrupt_Companies__c WHERE Case_Number__c = '{_soql_escape(str(case_number))}'"
        res = _sf_retry(self._sf.query, soql)
        records = res.get("records") or []
        if not records:
            raise _FatalSalesforceError(f"Bankrupt_Companies__c upsert succeeded but Id lookup failed for {case_number}")
        return records[0]["Id"]

    # -- account match (FR-5.1 — the swappable seam) --------------------------
    def _find_account(self, creditor: dict[str, Any]) -> str | None:
        """Return an existing Account Id, or None to create. Raises _ManualReview if ambiguous.

        Name-first (case-insensitive in SF), state only as a tiebreaker — so a
        sparse BillingState never causes a miss/duplicate.
        """
        names = [creditor.get("normalized_name"), creditor.get("creditor_name")]
        state = (creditor.get("creditor_state") or "").strip()
        for name in names:
            if not name or not name.strip():
                continue
            soql = (f"SELECT Id, BillingState FROM Account "
                    f"WHERE Name = '{_soql_escape(name.strip())}'")
            records = (_sf_retry(self._sf.query, soql).get("records") or [])
            if not records:
                continue
            if len(records) == 1:
                return records[0]["Id"]
            # Ambiguous on name → disambiguate by state when we have one.
            if state:
                by_state = [r for r in records if (r.get("BillingState") or "").strip().upper() == state.upper()]
                if len(by_state) == 1:
                    return by_state[0]["Id"]
            raise _ManualReview(
                f"{len(records)} Accounts named {name.strip()!r}"
                + (f" (state {state})" if state else "") + " — manual review"
            )
        return None  # no match on any name → caller creates

    def _account_fields(self, creditor: dict[str, Any], enrichment: dict[str, Any]) -> dict[str, Any]:
        fields: dict[str, Any] = {}
        state = (creditor.get("creditor_state") or "").strip()
        if state:
            fields["BillingState"] = state
        tier = _tier_label(enrichment.get("company_tier"))
        if tier:
            fields["Company_Tier__c"] = tier
        url = _zoominfo_url(enrichment.get("zoominfo_company_id"))
        if url:
            fields["ZoomInfo__c"] = url
        return fields

    def _match_or_create_account(self, creditor: dict[str, Any], enrichment: dict[str, Any]) -> str:
        account_id = self._find_account(creditor)  # may raise _ManualReview
        fields = self._account_fields(creditor, enrichment)
        if account_id:
            if fields:
                _sf_retry(self._sf.Account.update, account_id, fields)
            return account_id
        name = (creditor.get("normalized_name") or creditor.get("creditor_name") or "").strip()
        if not name:
            raise _ManualReview("creditor has no usable name")
        created = _sf_retry(self._sf.Account.create, {"Name": name[:255], **fields})
        return created["id"]

    # -- creditor row (Bankruptcy__c, the "Creditors" related list) -----------
    def _upsert_creditor_row(self, account_id: str, bc_id: str, b: dict[str, Any],
                             creditor: dict[str, Any]) -> None:
        # No external id on this object → query-then-write. Race-free only because
        # the worker runs a single sequential drain loop (no concurrent pushes).
        soql = (f"SELECT Id FROM Bankruptcy__c "
                f"WHERE Account__c = '{_soql_escape(account_id)}' "
                f"AND Bankrupt_Company__c = '{_soql_escape(bc_id)}'")
        existing = (_sf_retry(self._sf.query, soql).get("records") or [])
        fields: dict[str, Any] = {
            "Account__c": account_id,
            "Bankrupt_Company__c": bc_id,
            "Amount__c": creditor.get("claim_amount"),
        }
        if b.get("filing_date"):
            fields["File_Date__c"] = b["filing_date"]
        chapter = _chapter_label(b.get("chapter_type"))
        if chapter:
            fields["Chapter__c"] = chapter
        obj = getattr(self._sf, "Bankruptcy__c")
        if existing:
            _sf_retry(obj.update, existing[0]["Id"], fields)
        else:
            _sf_retry(obj.create, fields)

    # -- recency (FR-5.5; OD-5 rules pending client confirm — default here) ---
    def _compute_recency(self, account_id: str) -> str:
        esc = _soql_escape(account_id)
        open_opp = _sf_retry(self._sf.query,
                             f"SELECT Id FROM Opportunity WHERE AccountId = '{esc}' AND IsClosed = false LIMIT 1")
        if (open_opp.get("totalSize") or 0) > 0:
            return RECENCY_EXISTING
        for sobj in ("Task", "Event"):
            recent = _sf_retry(self._sf.query,
                               f"SELECT Id FROM {sobj} WHERE AccountId = '{esc}' "
                               f"AND CreatedDate = LAST_N_DAYS:90 LIMIT 1")
            if (recent.get("totalSize") or 0) > 0:
                return RECENCY_EXISTING
        return RECENCY_NEW

    # -- per-creditor orchestration ------------------------------------------
    def _push_creditor(self, b: dict[str, Any], bc_id: str, creditor: dict[str, Any],
                       enrichment: dict[str, Any]) -> None:
        account_id = self._match_or_create_account(creditor, enrichment)
        self._upsert_creditor_row(account_id, bc_id, b, creditor)
        recency = self._compute_recency(account_id)
        _persist_account_map(creditor["creditor_id"], account_id, recency,
                             self._url, self._key, self._t)

    def push_bankruptcy(self, b: dict[str, Any], creditors: list[dict[str, Any]],
                        enrichment: dict[str, dict[str, Any]]) -> PushResult:
        bc_id = self._upsert_debtor(b)
        result = PushResult()
        for creditor in creditors:
            cid = creditor.get("creditor_id", "?")
            try:
                self._push_creditor(b, bc_id, creditor, enrichment.get(cid, {}))
                result.pushed += 1
            except _ManualReview as mr:
                logger.warning("Creditor %s → manual review: %s", cid, mr)
                result.manual_review.append(str(cid))
            except Exception as exc:  # noqa: BLE001 — isolate one creditor's failure
                logger.error("Creditor %s push failed: %s", cid, exc)
                result.failed.append(str(cid))
        return result


# ---------------------------------------------------------------------------
# Salesforce client builder (lazy import so the module loads without the dep)
# ---------------------------------------------------------------------------

def _build_sf_client(settings: PipelineSettings) -> Any:
    from simple_salesforce import Salesforce  # lazy: only needed when actually pushing
    return Salesforce(
        username=settings.salesforce_username,
        password=settings.salesforce_password,
        security_token=settings.salesforce_security_token,
        domain=settings.salesforce_domain or "login",
    )


# ---------------------------------------------------------------------------
# Worker entry point
# ---------------------------------------------------------------------------

def process_job(job: dict[str, Any]) -> None:
    """Process one salesforce_push job. Called by worker._dispatch.

    Normal return → worker marks the job completed.
    _FatalSalesforceError / RuntimeError → worker marks failed + alerts.
    """
    settings = get_pipeline_settings()
    sb_url, sb_key, sb_t = settings.supabase_url, settings.supabase_service_role_key, settings.supabase_http_timeout_sec

    job_id = str(job.get("id", "?"))
    bankruptcy_id = job.get("bankruptcy_id")
    if not bankruptcy_id:
        raise _FatalSalesforceError(f"salesforce_push job {job_id} has no bankruptcy_id")

    # Guard: SKIP_SF is the intended gate; if it is off but creds are absent
    # that is a misconfiguration — fail loudly so the operator notices.
    if not (settings.salesforce_username and settings.salesforce_password):
        raise _FatalSalesforceError("Salesforce credentials not set (SALESFORCE_USERNAME/PASSWORD)")

    bankruptcy = _get_bankruptcy(str(bankruptcy_id), sb_url, sb_key, sb_t)
    if not bankruptcy:
        raise _FatalSalesforceError(f"no bankruptcies row for {bankruptcy_id}")

    creditors = _list_company_creditors(str(bankruptcy_id), sb_url, sb_key, sb_t)
    if not creditors:
        logger.info("No company creditors for %s — nothing to push", bankruptcy_id)
        return  # worker completes the job

    enrichment = _get_enrichment([c["creditor_id"] for c in creditors], sb_url, sb_key, sb_t)

    sf = _build_sf_client(settings)
    pusher = SalesforcePusher(sf, sb_url, sb_key, sb_t)
    result = pusher.push_bankruptcy(bankruptcy, creditors, enrichment)

    logger.info("salesforce_push for %s: pushed=%d manual_review=%d failed=%d",
                bankruptcy_id, result.pushed, len(result.manual_review), len(result.failed))

    # If nothing succeeded and something errored (vs all manual-review), surface it.
    if result.pushed == 0 and result.failed:
        raise RuntimeError(
            f"salesforce_push pushed 0/{len(creditors)} creditors for {bankruptcy_id} "
            f"(failed={len(result.failed)}, manual_review={len(result.manual_review)})"
        )
    return  # worker marks job completed; per-creditor failures are logged + reported
