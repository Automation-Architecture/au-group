"""Pipeline Salesforce push stage — WP-09 (KD-68).

The worker dispatches ``salesforce_push`` jobs here (gated by ``SKIP_SF``; the
worker requeues while that flag is set).  For each job — one per bankruptcy —
this stage pushes every enriched **company** creditor into the client's live
Salesforce org, against the org's CONFIRMED existing schema (see
``docs/project/salesforce-audit.md`` §1c — do NOT create ``Bankruptcy_Event__c``):

  1. Upsert the debtor as ``Bankrupt_Companies__c`` keyed on ``Case_Number__c``,
     with a name-match-and-backfill fallback for the pre-existing debtor rows the
     client maintains without case numbers (audit §1c) so we don't duplicate them.
  2. Match-or-create the creditor ``Account`` (FR-5.1 dedup against the client's
     ~13.5k existing accounts), set ``Company_Tier__c`` + ``ZoomInfo__c``.
  3. Create the creditor row as ``Bankruptcy__c`` (the "Creditors" related list:
     Account__c + Bankrupt_Company__c + Amount__c) — dedup query-then-write.
  4. Compute the FR-5.5 recency flag and persist it (RPC then PATCH).

Auth is username + password + security token (no Connected App yet — MVP).

Account match (the FR-5.1 crux) is isolated in ``_find_account`` so the strategy
can be swapped once measured against the live org with real creditor data.
Current strategy: exact Name match (SF Name match is case-insensitive),
disambiguated by BillingState only when Name is ambiguous (state-name/abbrev
tolerant) — so it does not depend on BillingState being populated.  0 matches →
create (a new lead); 1 → reuse; >1 unresolved across all candidate names → flag
manual review and skip (never guess which account, EC-3.1).

Two distinct creditors in one filing that resolve to the SAME Salesforce Account
are collapsed (the second is skipped as a duplicate) — both because the
``salesforce_accounts.salesforce_account_id`` column is UNIQUE (one account maps
to one creditor) and to avoid one creditor's ``Amount__c`` overwriting another's
on a shared ``Bankruptcy__c`` row.

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

import httpx

from pipeline.alerts import send_error_alert
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
# can zero the delay). Applied ONLY to idempotent calls (query/update/upsert) —
# never to create(), where a post-commit retry would duplicate a record.
_SF_MAX_ATTEMPTS = 3
_SF_RETRY_BASE_SEC = 1.0

# Full US state/territory name → USPS abbreviation, for the BillingState tiebreak
# (SF orgs store either form). Keyed lowercase.
_US_STATES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "district of columbia": "DC", "florida": "FL", "georgia": "GA", "hawaii": "HI",
    "idaho": "ID", "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY", "puerto rico": "PR",
}


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
    # company_tier is a smallint; reject non-integers (a float would truncate wrongly).
    if isinstance(company_tier, bool) or not isinstance(company_tier, int):
        if isinstance(company_tier, str) and company_tier.strip().isdigit():
            company_tier = int(company_tier)
        else:
            return None
    return _TIER_MAP.get(company_tier)


def _state_key(value: str | None) -> str:
    """Normalise a state to its USPS abbreviation for comparison ('' if unknown/blank)."""
    s = (value or "").strip()
    if not s:
        return ""
    if len(s) == 2:
        return s.upper()
    return _US_STATES.get(s.lower(), s.upper())


def _is_sf_transient(exc: Exception) -> bool:
    """503/5xx/429 from Salesforce (or a network error) is worth retrying."""
    status = getattr(exc, "status", None)
    if isinstance(status, int):
        return status == 429 or 500 <= status < 600
    return isinstance(exc, httpx.RequestError)


def _sf_retry(fn, *args, **kwargs):
    """Call an IDEMPOTENT fn with exponential backoff on transient Salesforce errors.

    Never wrap create(): a transient error after Salesforce has committed the
    write would duplicate the record on retry.
    """
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
    duplicates: list[str] = field(default_factory=list)  # collapsed onto another creditor's Account


# ---------------------------------------------------------------------------
# The pusher (takes a duck-typed simple-salesforce client — injected for tests)
# ---------------------------------------------------------------------------

class SalesforcePusher:
    """Pushes one filing's creditors into Salesforce via an injected ``sf`` client.

    ``sf`` must quack like simple_salesforce.Salesforce: ``sf.query(soql)`` and
    per-object accessors (``sf.Account``, ``getattr(sf, 'Bankruptcy__c')`` …)
    with ``.create(dict)`` / ``.update(id, dict)``.
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
        esc_case = _soql_escape(str(case_number))

        # 1. A row already keyed on this case number → update it.
        existing = (_sf_retry(self._sf.query,
                    f"SELECT Id FROM Bankrupt_Companies__c WHERE Case_Number__c = '{esc_case}'"
                    ).get("records") or [])
        if existing:
            _sf_retry(obj.update, existing[0]["Id"], fields)
            return existing[0]["Id"]

        # 2. A pre-existing debtor the client maintains WITHOUT a case number
        #    (audit §1c: 82 such rows) — match by name and backfill, don't dup.
        name = (b.get("debtor_name") or "").strip()
        if name:
            by_name = (_sf_retry(self._sf.query,
                       f"SELECT Id FROM Bankrupt_Companies__c "
                       f"WHERE Name = '{_soql_escape(name)}' AND Case_Number__c = null"
                       ).get("records") or [])
            if len(by_name) == 1:
                _sf_retry(obj.update, by_name[0]["Id"], {**fields, "Case_Number__c": str(case_number)})
                return by_name[0]["Id"]

        # 3. Genuinely new debtor. create() is not retried (idempotency).
        created = obj.create({**fields, "Case_Number__c": str(case_number)})
        return created["id"]

    # -- account match (FR-5.1 — the swappable seam) --------------------------
    def _disambiguate_by_state(self, records: list[dict[str, Any]], state: str) -> str | None:
        key = _state_key(state)
        if not key:
            return None
        matches = [r for r in records if _state_key(r.get("BillingState")) == key]
        return matches[0]["Id"] if len(matches) == 1 else None

    def _find_account(self, creditor: dict[str, Any]) -> str | None:
        """Return an existing Account Id, or None to create. Raises _ManualReview if ambiguous.

        Tries each candidate name (normalized then raw); only escalates to manual
        review if NO name yields a clean single match — an ambiguous normalized
        name still falls through to the raw name.
        """
        state = (creditor.get("creditor_state") or "").strip()
        ambiguous = False
        tried: set[str] = set()
        for raw in (creditor.get("normalized_name"), creditor.get("creditor_name")):
            name = (raw or "").strip()
            if not name or name.upper() in tried:
                continue
            tried.add(name.upper())
            records = (_sf_retry(self._sf.query,
                       f"SELECT Id, BillingState FROM Account WHERE Name = '{_soql_escape(name)}'"
                       ).get("records") or [])
            if not records:
                continue
            if len(records) == 1:
                return records[0]["Id"]
            resolved = self._disambiguate_by_state(records, state)
            if resolved:
                return resolved
            ambiguous = True  # remember, but keep trying the next candidate name
        if ambiguous:
            raise _ManualReview(f"creditor {creditor.get('creditor_id')} matches multiple Accounts")
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
        created = self._sf.Account.create({"Name": name[:255], **fields})  # not retried (idempotency)
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
            obj.create(fields)  # not retried (idempotency)

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

    # -- per-filing orchestration --------------------------------------------
    def push_bankruptcy(self, b: dict[str, Any], creditors: list[dict[str, Any]],
                        enrichment: dict[str, dict[str, Any]]) -> PushResult:
        bc_id = self._upsert_debtor(b)
        result = PushResult()
        seen_accounts: dict[str, str] = {}  # account_id → first creditor_id that claimed it
        for creditor in creditors:
            cid = str(creditor.get("creditor_id", "?"))
            try:
                account_id = self._match_or_create_account(creditor, enrichment.get(cid, {}))
                if account_id in seen_accounts:
                    # Two creditors in one filing → one Account: collapse the
                    # second (avoids the Amount__c clobber and the
                    # salesforce_account_id UNIQUE violation on persist).
                    logger.warning("Creditor %s resolves to the same Account %s as creditor %s — skipping duplicate",
                                   cid, account_id, seen_accounts[account_id])
                    result.duplicates.append(cid)
                    continue
                seen_accounts[account_id] = cid
                self._upsert_creditor_row(account_id, bc_id, b, creditor)
                recency = self._compute_recency(account_id)
                _persist_account_map(cid, account_id, recency, self._url, self._key, self._t)
                result.pushed += 1
            except _ManualReview as mr:
                logger.warning("Creditor %s → manual review: %s", cid, mr)
                result.manual_review.append(cid)
            except Exception as exc:  # noqa: BLE001 — isolate one creditor's failure
                logger.error("Creditor %s push failed: %s", cid, exc)
                result.failed.append(cid)
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
    Partial failures (some creditors pushed, some not) complete the job but fire
    a non-fatal Slack alert so the un-synced/manual-review creditors are surfaced.
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

    logger.info("salesforce_push for %s: pushed=%d manual_review=%d failed=%d duplicates=%d",
                bankruptcy_id, result.pushed, len(result.manual_review),
                len(result.failed), len(result.duplicates))

    # Nothing succeeded but something errored → surface as a job failure.
    if result.pushed == 0 and result.failed:
        raise RuntimeError(
            f"salesforce_push pushed 0/{len(creditors)} creditors for {bankruptcy_id} "
            f"(failed={len(result.failed)}, manual_review={len(result.manual_review)})"
        )

    # Partial success: complete the job but surface the stragglers (no auto-retry
    # exists per-creditor, so an alert is the durable signal — EC-3.1).
    if result.failed or result.manual_review:
        send_error_alert(
            stage="salesforce.py — partial push",
            error=(f"{bankruptcy_id}: pushed {result.pushed}/{len(creditors)}; "
                   f"failed={result.failed} manual_review={result.manual_review}"),
            bankruptcy_id=str(bankruptcy_id),
            bot_token=settings.slack_bot_token,
            channel_id=settings.slack_channel_id,
        )
    return  # worker marks job completed
