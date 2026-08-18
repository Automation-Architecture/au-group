"""PACER intake — WP-05a/b (KD-63 + KD-64).

Authenticates to PACER via the PCL REST API, discovers new Chapter 11 filings
in target states, and stores the Form 204 (top-20 creditor list) PDF in S3.

This module covers KD-63 (T-07a): auth + discovery + S3 upload.
KD-64 (T-08) adds: bankruptcy upsert, job enqueue, pacer_poll row, Railway cron.

API references: docs/architecture/pacer-pcl-api-reference.md
Spec: docs/architecture/n8n-to-code-native-migration.md §4.2 Stage 0

Invoked by the intake-cron Railway cron service (KD-64):
    python -m pipeline.intake [--dry-run]

Railway cron config (set in KD-64):
    rootDirectory:  services/document-parser
    startCommand:   python -m pipeline.intake
    schedule:       0 9 * * 1-5   (4 AM ET standard / OD-1 pending)
    No port binding.

NOTE on Form 204 download (UNVERIFIED):
    PCL REST provides case metadata and a caseLink CM/ECF URL per case.
    Document download requires following that court-specific URL with the PACER
    session token as a cookie.  The download implementation here is best-effort
    and must be validated against a live PACER account before production use.
    See _download_form_204() for the clearly marked UNVERIFIED section.
"""

from __future__ import annotations

import json
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

import boto3
import httpx
from botocore.exceptions import ClientError

from pipeline.alerts import send_error_alert
from pipeline.discovery import CourtListenerDiscoverer
from pipeline.ratelimit import (
    BudgetExhausted,
    get_courtlistener_limiter,
    reset_courtlistener_limiter,
)
from pipeline.retrieval import (
    CaseRef,
    CompositeRetriever,
    PacerCmecfRetriever,
    RecapRetriever,
)
from pipeline.settings import get_pipeline_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PCL REST API constants
# ---------------------------------------------------------------------------

_AUTH_URL   = "https://pacer.login.uscourts.gov/services/cso-auth"
_SEARCH_URL = "https://pcl.uscourts.gov/pcl-public-api/rest/cases/find"
_PAGE_SIZE  = 54  # PCL returns max 54 per immediate search page

# CourtListener discovery: re-query a few days behind the last-run watermark so
# boundary-exclusive date filters and CourtListener's same-day ingestion lag
# don't drop filings. Re-processing the overlap is free (idempotency gate).
_CL_LOOKBACK_DAYS = 3

# court_id values as stored in au_group_court_mappings (without 'bk' suffix).
# PCL requires the 'bk' suffix — we append it at call time.
# NOTE: 'maeb' in the DB is a data error; correct PACER ID for Michigan Eastern
# is 'mieb'.  This mapping uses the correct PACER IDs regardless of DB state.
_STATE_TO_COURT_IDS: dict[str, list[str]] = {
    "NY": ["nysb", "nyeb"],          # Southern + Eastern (largest Ch11 volume)
    "NJ": ["njb"],
    "PA": ["paeb", "pawb"],
    "FL": ["flsb", "flmb", "flnb"],
    "MI": ["mieb", "miwb"],
    # Expansion states (inactive by default; enable via au_group_target_states):
    "TX": ["txsb", "txnb"],
    "DE": ["deb"],
}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class PacerCase:
    """Minimal case record returned by the PCL case search."""
    court_id: str           # PCL court ID with 'bk' suffix (e.g. 'nysbk')
    case_id: int
    case_number_full: str   # e.g. '1:26bk12345'
    case_title: str         # debtor name
    date_filed: str         # 'YYYY-MM-DD'
    case_link: str          # CM/ECF docket URL — used for Form 204 download


@dataclass
class IntakeResult:
    cases_found: int = 0
    cases_uploaded: int = 0
    cases_skipped: int = 0
    errors: list[str] = field(default_factory=list)
    # KD-83: cases whose Form 204 lookup was never attempted because the shared
    # CourtListener budget ran out. UNKNOWN, not "not found" — they are left for
    # the next run by holding the watermark, and must never be counted as misses.
    cases_unattempted: int = 0
    budget_exhausted: bool = False
    # Cases skipped without spending quota because a previous run already looked
    # them up and found nothing (see the known-miss ledger).
    cases_known_missing: int = 0


# ---------------------------------------------------------------------------
# PACER client
# ---------------------------------------------------------------------------

class PacerClient:
    """PCL REST API client.

    Auth: POST https://pacer.login.uscourts.gov/services/cso-auth
    Case search: POST https://pcl.uscourts.gov/pcl-public-api/rest/cases/find
    Token refresh: response X-NEXT-GEN-CSO header carries a refreshed token.

    See docs/architecture/pacer-pcl-api-reference.md for full API spec.
    """

    def __init__(self, username: str, password: str, timeout: float = 30.0) -> None:
        self._username = username
        self._password = password
        self._timeout  = timeout
        self._token: str | None = None

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(self) -> str:
        """Obtain a nextGenCSO token from the PACER auth service.

        Response loginResult: '0' = success, anything else = failure.
        Token is valid for a session; reuse it until the response header
        returns a new one.
        """
        resp = httpx.post(
            _AUTH_URL,
            json={
                "loginId":    self._username,
                "password":   self._password,
                "redactFlag": "1",
            },
            timeout=self._timeout,
        )
        resp.raise_for_status()
        body = resp.json()
        login_result = body.get("loginResult", "")
        if login_result != "0":
            raise RuntimeError(
                f"PACER auth failed: loginResult={login_result!r} "
                f"errorDescription={body.get('errorDescription', '')!r}"
            )
        token = body.get("nextGenCSO", "")
        if not token:
            raise RuntimeError("PACER auth succeeded but returned no nextGenCSO token")
        self._token = token
        logger.info("PACER authenticated (token length=%d)", len(token))
        return token

    def _token_headers(self, token: str) -> dict[str, str]:
        return {
            "X-NEXT-GEN-CSO": token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------
    # Case search
    # ------------------------------------------------------------------

    def search_new_cases(
        self,
        court_ids: list[str],        # DB court IDs WITHOUT 'bk' suffix
        date_from: date,
        date_to: date,
        chapter: int = 11,
        token: str | None = None,
    ) -> tuple[list[PacerCase], str]:
        """Search for new Chapter 11 cases across the given courts.

        Returns (cases, refreshed_token).  Paginates until all pages fetched.
        PCL charges per page retrieved — use date ranges to limit scope.
        """
        tok = token or self._token
        if not tok:
            tok = self.authenticate()

        # PCL bankruptcy courtId = DB court_id + "k"
        # e.g. "nysb" → "nysbk", "njb" → "njbk"  (NOT "bk" — that gives "nysbbk")
        pcl_court_ids = [cid + "k" for cid in court_ids]
        body = {
            "jurisdictionType":       "bk",
            "federalBankruptcyChapter": [str(chapter)],
            "courtId":                pcl_court_ids,
            "dateFiledFrom":          date_from.isoformat(),
            "dateFiledTo":            date_to.isoformat(),
        }

        cases: list[PacerCase] = []
        page = 0

        while True:
            resp = httpx.post(
                f"{_SEARCH_URL}?page={page}",
                headers=self._token_headers(tok),
                json=body,
                timeout=self._timeout,
            )
            if resp.status_code == 401:
                logger.info("PACER token expired, re-authenticating")
                tok = self.authenticate()
                resp = httpx.post(
                    f"{_SEARCH_URL}?page={page}",
                    headers=self._token_headers(tok),
                    json=body,
                    timeout=self._timeout,
                )
            resp.raise_for_status()

            # Refresh token from response header if provided
            new_token = resp.headers.get("X-NEXT-GEN-CSO")
            if new_token:
                tok = new_token
                self._token = tok

            data = resp.json()
            content = data.get("content") or []
            for c in content:
                case_link = c.get("caseLink", "")
                if not case_link:
                    continue
                cases.append(PacerCase(
                    court_id=c.get("courtId", ""),
                    case_id=c.get("caseId", 0),
                    case_number_full=c.get("caseNumberFull", ""),
                    case_title=c.get("caseTitle", ""),
                    date_filed=c.get("dateFiled", ""),
                    case_link=case_link,
                ))

            page_info = data.get("pageInfo", {})
            total_pages = page_info.get("totalPages", 1)
            logger.info(
                "PCL search page %d/%d: %d cases (total so far: %d)",
                page + 1, total_pages, len(content), len(cases),
            )
            if page + 1 >= total_pages:
                break
            page += 1

        return cases, tok

    # ------------------------------------------------------------------
    # Form 204 download (CM/ECF)
    # UNVERIFIED: requires live PACER account test before production use.
    # PCL provides the caseLink docket URL; Form 204 must be found in the
    # docket HTML and downloaded with the PACER session cookie.
    # ------------------------------------------------------------------

    def download_form_204(self, case_link: str, token: str) -> bytes | None:
        """Download the Form 204 (top-20 creditor list) PDF from CM/ECF.

        UNVERIFIED — cannot validate without live PACER credentials against
        the production CM/ECF system.  The approach:
          1. GET the docket page at case_link with PacerSession cookie.
          2. Parse HTML for a link whose label matches common Form 204 names
             ('Top 20', 'B104', '20 Largest', 'Creditor Matrix').
          3. GET that document URL to obtain the PDF.

        Returns PDF bytes, or None if Form 204 was not found in the docket.
        """
        cookies = {"PacerSession": token}

        try:
            docket_resp = httpx.get(
                case_link,
                cookies=cookies,
                follow_redirects=True,
                timeout=self._timeout,
            )
            docket_resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("CM/ECF docket GET failed for %s: %s", case_link, exc)
            return None

        doc_url = _find_form_204_url(docket_resp.text, case_link)
        if not doc_url:
            logger.warning("Form 204 not found in docket: %s", case_link)
            return None

        try:
            pdf_resp = httpx.get(
                doc_url,
                cookies=cookies,
                follow_redirects=True,
                timeout=60.0,
            )
            pdf_resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Form 204 PDF download failed from %s: %s", doc_url, exc)
            return None

        content_type = pdf_resp.headers.get("content-type", "")
        if "pdf" not in content_type.lower() and "octet-stream" not in content_type.lower():
            logger.warning(
                "Form 204 response is not a PDF (content-type=%s): %s",
                content_type, doc_url,
            )
            return None

        return pdf_resp.content


def _find_form_204_url(html: str, base_url: str) -> str | None:
    """Scan CM/ECF docket HTML for a link that looks like Form 204.

    Matches link text containing common Form 204 identifiers (case-insensitive).
    Returns the absolute URL of the first match, or None.
    """
    _FORM_204_PATTERNS = re.compile(
        r"top\s+20|b\s*104|20\s+largest|creditor\s+(list|matrix|schedule)|"
        r"unsecured\s+creditors|form\s+204",
        re.IGNORECASE,
    )

    # Extract all anchor tags with href and link text
    anchor_re = re.compile(
        r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    for match in anchor_re.finditer(html):
        href, text = match.group(1), match.group(2)
        clean_text = re.sub(r"<[^>]+>", "", text).strip()
        if _FORM_204_PATTERNS.search(clean_text):
            # Make absolute if relative
            if href.startswith("http"):
                return href
            from urllib.parse import urljoin
            return urljoin(base_url, href)

    return None


# ---------------------------------------------------------------------------
# S3 upload helper (uses pipeline settings, not app settings)
# ---------------------------------------------------------------------------

class _PipelineS3:
    """Minimal S3 client using pipeline settings (not app Settings)."""

    def __init__(self) -> None:
        s = get_pipeline_settings()
        kwargs: dict = {"region_name": s.aws_region}
        if s.s3_endpoint:
            kwargs["endpoint_url"] = s.s3_endpoint.rstrip("/")
        if s.aws_access_key_id and s.aws_secret_access_key:
            kwargs["aws_access_key_id"]     = s.aws_access_key_id
            kwargs["aws_secret_access_key"] = s.aws_secret_access_key
        self._client = boto3.client("s3", **kwargs)
        self._bucket = s.s3_bucket

    def put_bytes(self, key: str, data: bytes, content_type: str = "application/pdf") -> None:
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    def key_exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

def _supabase_headers(service_role_key: str) -> dict[str, str]:
    return {
        "apikey":        service_role_key,
        "Authorization": f"Bearer {service_role_key}",
        "Content-Type":  "application/json",
    }


def _get_active_court_ids(supabase_url: str, key: str, timeout: float) -> list[str]:
    """Return active court IDs from au_group_court_mappings joined with target states."""
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(
            f"{supabase_url.rstrip('/')}/rest/v1/au_group_court_mappings",
            headers=_supabase_headers(key),
            params={
                "select": "court_id,state",
                "active": "eq.true",
            },
        )
        resp.raise_for_status()
        rows = resp.json()

    # Filter to states that are active in au_group_target_states
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(
            f"{supabase_url.rstrip('/')}/rest/v1/au_group_target_states",
            headers=_supabase_headers(key),
            params={"select": "state", "active": "eq.true"},
        )
        resp.raise_for_status()
        active_states = {r["state"] for r in resp.json()}

    return [_correct_court_id(r["court_id"]) for r in rows if r["state"] in active_states]


def _get_last_run_date(supabase_url: str, key: str, timeout: float) -> date:
    """Return the date of the last successful intake run, or 7 days ago."""
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(
            f"{supabase_url.rstrip('/')}/rest/v1/au_group_runtime_config",
            headers=_supabase_headers(key),
            params={"select": "config_value", "config_key": "eq.intake_last_run_at"},
        )
        resp.raise_for_status()
        rows = resp.json()

    if rows:
        try:
            return date.fromisoformat(rows[0]["config_value"][:10])
        except (ValueError, KeyError):
            pass

    # Default: look back 7 days on first run
    from datetime import timedelta
    return date.today() - timedelta(days=7)


def _set_last_run_date(supabase_url: str, key: str, timeout: float, run_date: date) -> None:
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(
            f"{supabase_url.rstrip('/')}/rest/v1/au_group_runtime_config",
            headers={**_supabase_headers(key), "Prefer": "resolution=merge-duplicates"},
            json={
                "config_key":   "intake_last_run_at",
                "config_value": run_date.isoformat(),
                "notes":        "set by pipeline/intake.py after successful run",
            },
        )
        resp.raise_for_status()


# ---------------------------------------------------------------------------
# S3 key helpers
# ---------------------------------------------------------------------------

def _form_204_s3_key(case_number_full: str) -> str:
    """Normalize case number for use as an S3 key component."""
    safe = re.sub(r"[^a-zA-Z0-9._-]", "-", case_number_full)
    return f"raw-documents/{safe}/form-204.pdf"


# ---------------------------------------------------------------------------
# Court mapping cache
# ---------------------------------------------------------------------------

# DB data bug: Michigan Eastern is stored as 'maeb'; correct PACER ID is 'mieb'.
def _correct_court_id(court_id: str) -> str:
    """Normalise a DB court_id to the real PACER court ID (no bk suffix)."""
    return "mieb" if court_id == "maeb" else court_id


def _get_court_mapping(supabase_url: str, key: str, timeout: float) -> dict[str, dict]:
    """Return {court_id: {state, court_district}} for all active courts."""
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(
            f"{supabase_url.rstrip('/')}/rest/v1/au_group_court_mappings",
            headers=_supabase_headers(key),
            params={"select": "court_id,state,court_district", "active": "eq.true"},
        )
        resp.raise_for_status()
    # Remap any known DB data errors so lookup keys match real PACER court IDs.
    return {_correct_court_id(r["court_id"]): r for r in resp.json()}


# ---------------------------------------------------------------------------
# Database operations (KD-64)
# ---------------------------------------------------------------------------

def _upsert_bankruptcy(
    case: PacerCase,
    court_mapping: dict[str, dict],
    supabase_url: str,
    key: str,
    timeout: float,
) -> str | None:
    """Call au_group_upsert_bankruptcy RPC. Returns bankruptcy UUID or None on error."""
    # Strip trailing 'k' to recover the DB court_id (e.g. nysbk → nysb),
    # then normalise via _correct_court_id so mieb/maeb resolve to the same key.
    db_court_id = _correct_court_id(
        case.court_id[:-1] if case.court_id.endswith("k") else case.court_id
    )
    court = court_mapping.get(db_court_id)
    if not court:
        raise ValueError(
            f"Missing court mapping for PACER court_id={case.court_id!r} "
            f"(resolved db_court_id={db_court_id!r})"
        )
    court_district = court["court_district"]
    state = court["state"]

    with httpx.Client(timeout=timeout) as client:
        resp = client.post(
            f"{supabase_url.rstrip('/')}/rest/v1/rpc/au_group_upsert_bankruptcy",
            headers={**_supabase_headers(key), "Prefer": "return=representation"},
            json={
                "p_case_number":    case.case_number_full,
                "p_debtor_name":    case.case_title,
                "p_filing_date":    case.date_filed,
                "p_court_district": court_district,
                "p_chapter_type":   "11",
                "p_state":          state,
            },
        )
        resp.raise_for_status()
    return resp.json()  # RPC returns the UUID as a plain string


def _enqueue_document_parse(
    bankruptcy_id: str,
    supabase_url: str,
    key: str,
    timeout: float,
) -> None:
    """Call au_group_enqueue_job for document_parse. No-ops if already queued/running."""
    # Migration: 20260530120001_au_group_enqueue_claim_job_rpcs.sql (PR #39)
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(
            f"{supabase_url.rstrip('/')}/rest/v1/rpc/au_group_enqueue_job",
            headers=_supabase_headers(key),
            json={"p_bankruptcy_id": bankruptcy_id, "p_job_type": "document_parse"},
        )
        resp.raise_for_status()
    result = resp.json()
    logger.debug("enqueue document_parse for %s: %s", bankruptcy_id, result)


def _insert_pacer_poll_job(
    bankruptcy_id: str,
    status: str,        # 'completed' or 'failed'
    supabase_url: str,
    key: str,
    timeout: float,
) -> None:
    """Insert a pacer_poll processing_job row per ADR-001."""
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(
            f"{supabase_url.rstrip('/')}/rest/v1/processing_jobs",
            headers=_supabase_headers(key),
            json={
                "job_type":      "pacer_poll",
                "status":        status,
                "bankruptcy_id": bankruptcy_id,
                "completed_at":  datetime.now(tz=UTC).isoformat(),
            },
        )
        resp.raise_for_status()


# ---------------------------------------------------------------------------
# Supabase existence check (used by compound idempotency gate)
# ---------------------------------------------------------------------------

def _bankruptcy_row_exists(case_number: str, supabase_url: str, key: str, timeout: float) -> str | None:
    """Return the bankruptcy UUID if a row exists for this case_number, or None."""
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(
            f"{supabase_url.rstrip('/')}/rest/v1/bankruptcies",
            headers={**_supabase_headers(key), "Prefer": "count=exact"},
            params={"select": "id", "case_number": f"eq.{case_number}", "limit": "1"},
        )
        resp.raise_for_status()
    rows = resp.json()
    return rows[0]["id"] if rows else None


# ---------------------------------------------------------------------------
# Known-miss ledger (KD-83)
# ---------------------------------------------------------------------------
# Under a CourtListener call budget a run only reaches part of the window, so
# the run needs to know which cases it has ALREADY looked up — otherwise every
# run spends its whole budget re-checking the same oldest cases and never
# reaches newer filings. A filing-date watermark cannot express this: the
# _CL_LOOKBACK_DAYS overlap means the attempted prefix usually sits at or before
# the watermark, so a date-based "partial advance" would rarely fire and the
# backlog would grow without bound.
#
# So misses are recorded per case in au_group_runtime_config (a plain key/value
# table — no schema change). SUCCESSES are deliberately NOT recorded: they are
# already handled by the S3-object + bankruptcy-row idempotency gate, which
# costs no CourtListener quota and preserves the re-enqueue recovery path.
_MISSED_LEDGER_KEY = "intake_missed_cases"
# RECAP is an upload-as-purchased archive, so a document absent today can appear
# later — retry a miss once on a later day, then stop paying for it.
_MISS_MAX_ATTEMPTS = 2
# Size control only: once the watermark has moved past a filing date, discovery
# never returns that case again, so an old entry can be dropped safely.
_LEDGER_RETENTION_DAYS = 45
_LEDGER_MAX_ENTRIES = 5000


def _should_skip_missed(entry: dict, today: date) -> bool:
    """True if this case was already looked up and must not spend quota again.

    Skips when the retry allowance is used up, or when it was already attempted
    today (a re-run on the same day must not re-check the same cases).
    """
    if not entry:
        return False
    if int(entry.get("attempts", 0)) >= _MISS_MAX_ATTEMPTS:
        return True
    return str(entry.get("last", "")) == today.isoformat()


def _prune_missed_ledger(ledger: dict[str, dict], today: date) -> dict[str, dict]:
    """Drop entries older than the retention window, then cap the total size."""
    cutoff = (today - timedelta(days=_LEDGER_RETENTION_DAYS)).isoformat()
    kept = {
        case: e for case, e in ledger.items()
        if str(e.get("filed") or e.get("last") or "") >= cutoff
    }
    if len(kept) > _LEDGER_MAX_ENTRIES:
        # Keep the most recently attempted — the oldest are the least likely to
        # be rediscovered at all.
        newest = sorted(kept.items(), key=lambda kv: str(kv[1].get("last", "")), reverse=True)
        kept = dict(newest[:_LEDGER_MAX_ENTRIES])
    return kept


def _record_miss(ledger: dict[str, dict], case_number: str, date_filed: str,
                 today: date) -> None:
    """Add or bump a case's miss entry in place."""
    entry = ledger.get(case_number) or {"filed": date_filed, "attempts": 0}
    entry["attempts"] = int(entry.get("attempts", 0)) + 1
    entry["last"] = today.isoformat()
    entry.setdefault("filed", date_filed)
    ledger[case_number] = entry


def _get_missed_ledger(supabase_url: str, key: str, timeout: float) -> dict[str, dict]:
    """Read the ledger; an unreadable/corrupt value degrades to empty, never raises.

    Losing the ledger costs quota (cases get re-checked), not correctness, so it
    must never be able to fail a run.
    """
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.get(
                f"{supabase_url.rstrip('/')}/rest/v1/au_group_runtime_config",
                headers=_supabase_headers(key),
                params={"select": "config_value", "config_key": f"eq.{_MISSED_LEDGER_KEY}"},
            )
            resp.raise_for_status()
            rows = resp.json()
        if not rows:
            return {}
        parsed = json.loads(rows[0]["config_value"] or "{}")
        if not isinstance(parsed, dict):
            return {}
        return {k: v for k, v in parsed.items() if isinstance(v, dict)}
    except Exception as exc:  # noqa: BLE001 — advisory cache, never fatal
        logger.warning("Could not read the known-miss ledger (re-checking everything): %s", exc)
        return {}


def _set_missed_ledger(supabase_url: str, key: str, timeout: float,
                       ledger: dict[str, dict]) -> None:
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(
            f"{supabase_url.rstrip('/')}/rest/v1/au_group_runtime_config",
            headers={**_supabase_headers(key), "Prefer": "resolution=merge-duplicates"},
            json={
                "config_key":   _MISSED_LEDGER_KEY,
                "config_value": json.dumps(ledger, separators=(",", ":")),
                "notes":        "cases whose Form 204 lookup came back empty (pipeline/intake.py)",
            },
        )
        resp.raise_for_status()


# ---------------------------------------------------------------------------
# Main intake runner (KD-63: discovery + S3; KD-64: persist + enqueue + alerts)
# ---------------------------------------------------------------------------

def run(dry_run: bool = False) -> IntakeResult:
    """Discover new Ch. 11 cases, upload Form 204, upsert DB rows, enqueue parse jobs.

    dry_run=True: logs discovery without writing to S3, Supabase, or runtime config.
    """
    settings = get_pipeline_settings()
    result   = IntakeResult()

    # Discovery source: PACER PCL (authoritative) when creds exist, else the free
    # CourtListener Search API (no standard PACER account needed — OD-8 resolution).
    has_pacer = bool(settings.pacer_username and settings.pacer_password)
    has_courtlistener = bool(settings.courtlistener_api_token)
    if not (has_pacer or has_courtlistener):
        logger.error("No discovery source — set PACER creds or COURTLISTENER_API_TOKEN")
        result.errors.append("fatal: no discovery source (PACER or CourtListener)")
        return result

    sb_url = settings.supabase_url
    sb_key = settings.supabase_service_role_key
    sb_t   = settings.supabase_http_timeout_sec

    # 1. Read config from Supabase
    try:
        court_ids     = _get_active_court_ids(sb_url, sb_key, sb_t)
        court_mapping = _get_court_mapping(sb_url, sb_key, sb_t)
        since         = _get_last_run_date(sb_url, sb_key, sb_t)
    except Exception as exc:
        logger.error("Failed to read Supabase config: %s", exc)
        send_error_alert(
            stage="intake.py — config read",
            error=str(exc),
            bot_token=settings.slack_bot_token,
            channel_id=settings.slack_channel_id,
        )
        result.errors.append(f"fatal: config read failed: {exc}")
        return result

    if not court_ids:
        logger.warning("No active court IDs in au_group_court_mappings — nothing to search")
        return result

    until = date.today()
    logger.info("Intake: %d courts | since=%s until=%s | source=%s | dry_run=%s",
                len(court_ids), since, until, "PACER" if has_pacer else "CourtListener", dry_run)

    # 2. Discover new Chapter 11 cases (PACER PCL if creds, else CourtListener).
    # ONE limiter for the whole run: discovery and Form 204 retrieval spend the
    # same CourtListener account quota (5/min, 50/hr). Giving each stage its own
    # would let both believe they had a full budget — which is how the 2026-08-17
    # run managed 493 x 429 and zero successful calls (KD-83).
    # Reset first: the singleton would otherwise carry a spent budget into a
    # second run() in the same process, which would report 100% unattempted and
    # alert "out of quota" without making a single call.
    reset_courtlistener_limiter()
    limiter = get_courtlistener_limiter(
        min_interval_sec=settings.courtlistener_min_interval_sec,
        per_minute=settings.courtlistener_rate_per_min,
        per_hour=settings.courtlistener_rate_per_hour,
        run_budget=settings.courtlistener_run_call_budget,
    )

    pacer: PacerClient | None = None
    token: str | None = None
    discovery_complete = True  # PACER raises on failure; CourtListener reports it
    try:
        if has_pacer:
            pacer = PacerClient(settings.pacer_username, settings.pacer_password)
            token = pacer.authenticate()
            cases, token = pacer.search_new_cases(
                court_ids=court_ids, date_from=since, date_to=until, chapter=11, token=token,
            )
        else:
            # Cap discovery's share of the shared budget. At 20 results/page an
            # uncapped 25-page walk could spend more than half the run's calls
            # before a single Form 204 lookup — and if pagination exhausted the
            # budget the watermark would be held and the next run would spend
            # its budget the same way, never reaching retrieval at all.
            discoverer = CourtListenerDiscoverer(
                settings.courtlistener_api_token, timeout=settings.courtlistener_timeout_sec,
                max_pages=settings.courtlistener_discovery_page_budget, limiter=limiter,
            )
            # Re-query a few days behind the watermark; re-processing is idempotent.
            cl_since = since - timedelta(days=_CL_LOOKBACK_DAYS)
            cases, discovery_complete = discoverer.discover(court_ids, cl_since, until, chapter=11)
    except Exception as exc:
        logger.error("Case discovery failed: %s", exc)
        send_error_alert(
            stage="intake.py — discovery",
            error=str(exc),
            bot_token=settings.slack_bot_token,
            channel_id=settings.slack_channel_id,
        )
        result.errors.append(f"fatal: discovery failed: {exc}")
        return result

    result.cases_found = len(cases)
    logger.info("Found %d new Chapter 11 cases", len(cases))

    if dry_run:
        for c in cases:
            logger.info("[DRY-RUN] %s | %s | filed %s", c.case_number_full, c.case_title, c.date_filed)
        return result

    # 4. Per-case: download Form 204 → S3 → upsert bankruptcy → enqueue → poll row
    s3 = _PipelineS3()

    # Cheapest-first Form 204 retrieval: free RECAP archive (when a CourtListener
    # token is configured) → paid PACER CM/ECF fetch (only when PACER creds +
    # session exist). See pipeline/retrieval.py.
    retrievers: list = []
    if settings.courtlistener_api_token:
        retrievers.append(RecapRetriever(
            settings.courtlistener_api_token, timeout=settings.courtlistener_timeout_sec,
            limiter=limiter,
        ))
    if has_pacer and pacer is not None and token is not None:
        retrievers.append(PacerCmecfRetriever(pacer, token))
    retriever = CompositeRetriever(retrievers)

    # Oldest first. Under a call budget a run only gets through part of the
    # window, so the order decides which cases are attempted — ascending drains
    # the backlog in filing order instead of starving the oldest cases forever.
    # (Discovery returns dateFiled desc.) Cases with no filing date sort first
    # and are harmless here; discovery already drops them.
    cases = sorted(cases, key=lambda c: c.date_filed)

    # Form 204 misses are reported ONCE at the end of the run. One Slack alert
    # per case posted ~52 red messages a day into the client-visible channel and
    # got alerting muted entirely on that service — see the KD-83 notes.
    missed_cases: list[str] = []
    # Any failure that is NOT "no Form 204 exists" — S3, upsert, enqueue. These
    # leave a case with no S3 object and no DB row, so the idempotency gate
    # cannot recover it; the watermark must be held so discovery returns it again.
    had_persist_errors = False

    ledger = _get_missed_ledger(sb_url, sb_key, sb_t)
    ledger_dirty = False

    for idx, case in enumerate(cases):
        # Already looked up and found empty on a previous run — skip before any
        # CourtListener call, so the budget goes to cases we know nothing about.
        if _should_skip_missed(ledger.get(case.case_number_full, {}), until):
            result.cases_known_missing += 1
            continue

        s3_key = _form_204_s3_key(case.case_number_full)

        # Compound idempotency gate: S3 key AND a persisted bankruptcy row.
        # If S3 upload succeeded but _upsert_bankruptcy() failed on a prior run,
        # s3.key_exists() alone would silently skip the case forever.
        # If both exist but enqueue never fired (prior run failed at that step),
        # call _enqueue_document_parse() — it no-ops if already queued/running.
        existing_id = _bankruptcy_row_exists(case.case_number_full, sb_url, sb_key, sb_t)
        if s3.key_exists(s3_key) and existing_id:
            try:
                _enqueue_document_parse(existing_id, sb_url, sb_key, sb_t)
            except Exception as exc:
                logger.warning("Idempotency re-enqueue failed for %s: %s", case.case_number_full, exc)
            logger.debug("Form 204 + DB row already present, skipping: %s", s3_key)
            result.cases_skipped += 1
            continue

        # 4a. Retrieve Form 204 — RECAP archive (free) → PACER CM/ECF (paid).
        # case.court_id carries the PCL 'k' suffix (e.g. 'nysbk'); RECAP/PACER
        # court ids drop it, so normalise the same way _upsert_bankruptcy does.
        db_court_id = _correct_court_id(
            case.court_id[:-1] if case.court_id.endswith("k") else case.court_id
        )
        try:
            retrieved = retriever.retrieve(CaseRef(
                court_id=db_court_id,
                case_number_full=case.case_number_full,
                debtor_name=case.case_title,
                case_link=case.case_link,
            ))
        except BudgetExhausted as exc:
            # Out of CourtListener quota. Every remaining case is UNKNOWN, not a
            # miss — stop here rather than log false misses (the 2026-08-17
            # failure mode). The watermark is held below so they stay
            # discoverable; the ledger is what stops the next run repeating this
            # run's work.
            result.budget_exhausted = True
            result.cases_unattempted = sum(
                1 for c in cases[idx:]
                if not _should_skip_missed(ledger.get(c.case_number_full, {}), until)
            )
            logger.warning("Retrieval stopped after %d/%d cases — %s "
                           "(%d unattempted, left for the next run)",
                           idx, len(cases), exc, result.cases_unattempted)
            break
        pdf_bytes = retrieved.pdf if retrieved else None
        if pdf_bytes is None:
            logger.warning("Form 204 not found for %s (%s)", case.case_number_full, case.case_title)
            result.errors.append(f"{case.case_number_full}: Form 204 not found")
            missed_cases.append(case.case_number_full)
            # A CONFIRMED absence (every configured source answered) — record it
            # so later runs spend their budget on cases they have not seen.
            _record_miss(ledger, case.case_number_full, case.date_filed, until)
            ledger_dirty = True
            result.cases_skipped += 1
            continue

        # 4b. Upload to S3
        try:
            s3.put_bytes(s3_key, pdf_bytes, content_type="application/pdf")
            logger.info("S3 ← %s (%d bytes) → %s", case.case_number_full, len(pdf_bytes), s3_key)
        except Exception as exc:
            logger.error("S3 upload failed for %s: %s", case.case_number_full, exc)
            result.errors.append(f"{case.case_number_full}: S3 upload failed")
            had_persist_errors = True
            send_error_alert(
                stage="intake.py — S3 upload",
                error=str(exc),
                bankruptcy_id=case.case_number_full,
                bot_token=settings.slack_bot_token,
                channel_id=settings.slack_channel_id,
            )
            result.cases_skipped += 1
            continue

        # 4c. Upsert bankruptcy row
        try:
            bankruptcy_id = _upsert_bankruptcy(case, court_mapping, sb_url, sb_key, sb_t)
        except Exception as exc:
            logger.error("Bankruptcy upsert failed for %s: %s", case.case_number_full, exc)
            send_error_alert(
                stage="intake.py — bankruptcy upsert",
                error=str(exc),
                bankruptcy_id=case.case_number_full,
                bot_token=settings.slack_bot_token,
                channel_id=settings.slack_channel_id,
            )
            result.errors.append(f"{case.case_number_full}: upsert failed")
            had_persist_errors = True
            result.cases_skipped += 1
            continue

        # 4d. Enqueue document_parse job
        try:
            _enqueue_document_parse(bankruptcy_id, sb_url, sb_key, sb_t)
        except Exception as exc:
            logger.error("Enqueue failed for %s (%s): %s", case.case_number_full, bankruptcy_id, exc)
            send_error_alert(
                stage="intake.py — enqueue",
                error=str(exc),
                bankruptcy_id=bankruptcy_id,
                bot_token=settings.slack_bot_token,
                channel_id=settings.slack_channel_id,
            )
            result.errors.append(f"{case.case_number_full}: enqueue failed")
            had_persist_errors = True
            try:
                _insert_pacer_poll_job(bankruptcy_id, "failed", sb_url, sb_key, sb_t)
            except Exception as poll_exc:
                logger.warning("failed pacer_poll row insert also failed for %s: %s", bankruptcy_id, poll_exc)
            result.cases_skipped += 1
            continue

        # 4e. Insert pacer_poll completed row (ADR-001)
        try:
            _insert_pacer_poll_job(bankruptcy_id, "completed", sb_url, sb_key, sb_t)
        except Exception as exc:
            logger.warning("pacer_poll row insert failed for %s: %s", bankruptcy_id, exc)

        result.cases_uploaded += 1
        logger.info("Processed %s → bankruptcy_id=%s (Form 204 via %s, %s)",
                    case.case_number_full, bankruptcy_id, retrieved.source, retrieved.cost_note)

    # 5. Update last run timestamp — ONLY if discovery fully covered the window.
    # Advancing the watermark after an incomplete discovery (outage / page cap)
    # would skip the un-fetched cases forever; leave it so the next run re-covers
    # (re-processing already-done cases is idempotent via the S3 + row gate).
    # Persist the known-miss ledger before anything else can fail — losing it
    # only costs quota next run, but writing it late risks losing this run's work.
    if ledger_dirty:
        try:
            _set_missed_ledger(sb_url, sb_key, sb_t, _prune_missed_ledger(ledger, until))
        except Exception as exc:  # noqa: BLE001 — advisory cache, never fatal
            logger.warning("Could not persist the known-miss ledger: %s", exc)

    # One summary alert for the run's Form 204 misses, not one per case. Per-case
    # alerting posted ~52 red messages a day into the client-visible channel and
    # got alerting on this service muted outright — see the KD-83 notes.
    if missed_cases:
        sample = ", ".join(missed_cases[:5])
        more = f" (+{len(missed_cases) - 5} more)" if len(missed_cases) > 5 else ""
        logger.warning("Form 204 not found for %d of %d attempted cases",
                       len(missed_cases), len(missed_cases) + result.cases_uploaded)
        send_error_alert(
            stage="intake.py — Form 204 retrieval",
            error=f"No Form 204 found via RECAP or CM/ECF for {len(missed_cases)} case(s) "
                  f"this run: {sample}{more}. Expected while RECAP coverage is ~1.6% "
                  f"(KD-75); not a pipeline fault.",
            bot_token=settings.slack_bot_token,
            channel_id=settings.slack_channel_id,
        )

    # 5. Advance the watermark ONLY when the window is genuinely finished.
    #
    # Forward progress under a call budget comes from the known-miss ledger, NOT
    # from moving the watermark over a partially-processed window: any case the
    # watermark passes is never rediscovered, so advancing over un-attempted or
    # failed cases loses them permanently.
    if not discovery_complete:
        logger.warning("Discovery incomplete — not advancing intake_last_run_at (window will be re-covered)")
        send_error_alert(
            stage="intake.py — incomplete discovery",
            error=f"CourtListener discovery did not fully cover the window since={since}; "
                  f"watermark held, {result.cases_uploaded} cases processed this run",
            bot_token=settings.slack_bot_token,
            channel_id=settings.slack_channel_id,
        )
    elif result.budget_exhausted:
        # Watermark HELD: the un-attempted tail must stay discoverable. The next
        # run skips this run's confirmed misses via the ledger, so it reaches
        # further into the backlog instead of re-checking the same cases.
        logger.warning("CourtListener budget exhausted after %d calls — %d cases unattempted, "
                       "watermark held", limiter.spent, result.cases_unattempted)
        send_error_alert(
            stage="intake.py — CourtListener budget",
            error=f"Ran out of CourtListener REST quota after {limiter.spent} calls. "
                  f"{result.cases_unattempted} case(s) were NOT attempted — unknown, not "
                  f"misses — and stay queued for the next run (watermark held at {since}). "
                  f"If this repeats daily the backlog exceeds the free quota: see KD-75.",
            bot_token=settings.slack_bot_token,
            channel_id=settings.slack_channel_id,
        )
    elif had_persist_errors:
        # S3 / upsert / enqueue failures leave no S3 object and no DB row, so the
        # idempotency gate cannot recover those cases — only rediscovery can.
        logger.warning("Persistence errors this run — holding intake_last_run_at so the "
                       "affected cases are rediscovered")
    else:
        # Every discovered case was attempted and everything persisted. Advance
        # even when nothing was found: without this, a window of genuine misses
        # is re-discovered and re-attempted every single day, burning the whole
        # budget on cases already known to be absent (what the 2026-08-17 run
        # did). The ledger keeps those misses cheap either way.
        try:
            _set_last_run_date(sb_url, sb_key, sb_t, until)
        except Exception as exc:
            logger.error("Failed to update intake_last_run_at: %s", exc)
            send_error_alert(
                stage="intake.py — set last run date",
                error=str(exc),
                bot_token=settings.slack_bot_token,
                channel_id=settings.slack_channel_id,
            )
            result.errors.append(f"non-fatal: intake_last_run_at update failed: {exc}")

    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    parser = argparse.ArgumentParser(description="AU Group PACER intake (KD-63)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Discover cases but do not write to S3 or update runtime config")
    args = parser.parse_args()

    result = run(dry_run=args.dry_run)
    logger.info(
        "Intake complete: found=%d uploaded=%d skipped=%d known_missing=%d "
        "unattempted=%d errors=%d budget_exhausted=%s",
        result.cases_found, result.cases_uploaded, result.cases_skipped,
        result.cases_known_missing, result.cases_unattempted, len(result.errors),
        result.budget_exhausted,
    )
    if result.errors:
        for err in result.errors:
            logger.warning("  - %s", err)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
