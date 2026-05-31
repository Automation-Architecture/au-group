"""PACER intake — WP-05a (KD-63).

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

import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Optional

import boto3
import httpx
from botocore.exceptions import ClientError

from pipeline.settings import get_pipeline_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# PCL REST API constants
# ---------------------------------------------------------------------------

_AUTH_URL   = "https://pacer.login.uscourts.gov/services/cso-auth"
_SEARCH_URL = "https://pcl.uscourts.gov/pcl-public-api/rest/cases/find"
_PAGE_SIZE  = 54  # PCL returns max 54 per immediate search page

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

        pcl_court_ids = [cid + "bk" for cid in court_ids]
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

    def download_form_204(self, case_link: str, token: str) -> Optional[bytes]:
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


def _find_form_204_url(html: str, base_url: str) -> Optional[str]:
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
        except ClientError:
            return False


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

    return [r["court_id"] for r in rows if r["state"] in active_states]


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
            f"{supabase_url.rstrip('/')}/rest/v1/rpc/au_group_upsert_runtime_config"
            if False  # fallback to direct upsert
            else f"{supabase_url.rstrip('/')}/rest/v1/au_group_runtime_config",
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
    return f"raw-documents/{safe}/form_204.pdf"


# ---------------------------------------------------------------------------
# Main intake runner (KD-63 scope: discovery + S3 upload)
# Database upsert + job enqueue + cron service are KD-64 (T-08).
# ---------------------------------------------------------------------------

def run(dry_run: bool = False) -> IntakeResult:
    """Discover new Ch. 11 cases and upload Form 204 PDFs to S3.

    dry_run=True: logs discovery without writing to S3 or updating runtime config.
    """
    settings = get_pipeline_settings()
    result   = IntakeResult()

    if not settings.pacer_username or not settings.pacer_password:
        logger.error("PACER_USERNAME / PACER_PASSWORD not set — cannot run intake")
        return result

    # 1. Read config from Supabase
    court_ids = _get_active_court_ids(
        settings.supabase_url, settings.supabase_service_role_key,
        settings.supabase_http_timeout_sec,
    )
    if not court_ids:
        logger.warning("No active court IDs found in au_group_court_mappings — nothing to search")
        return result

    since = _get_last_run_date(
        settings.supabase_url, settings.supabase_service_role_key,
        settings.supabase_http_timeout_sec,
    )
    until = date.today()
    logger.info("Intake: courts=%s since=%s until=%s dry_run=%s", court_ids, since, until, dry_run)

    # 2. Authenticate to PACER
    pacer  = PacerClient(settings.pacer_username, settings.pacer_password)
    token  = pacer.authenticate()

    # 3. Search for new cases
    cases, token = pacer.search_new_cases(
        court_ids=court_ids,
        date_from=since,
        date_to=until,
        chapter=11,
        token=token,
    )
    result.cases_found = len(cases)
    logger.info("Found %d new Chapter 11 cases", len(cases))

    if dry_run:
        for c in cases:
            logger.info(
                "[DRY-RUN] Would upload Form 204 for: %s | %s | filed %s",
                c.case_number_full, c.case_title, c.date_filed,
            )
        return result

    # 4. Download Form 204 + upload to S3
    s3 = _PipelineS3()

    for case in cases:
        s3_key = _form_204_s3_key(case.case_number_full)

        if s3.key_exists(s3_key):
            logger.debug("Form 204 already in S3, skipping: %s", s3_key)
            result.cases_skipped += 1
            continue

        pdf_bytes = pacer.download_form_204(case.case_link, token)
        if pdf_bytes is None:
            logger.warning(
                "Form 204 download failed for %s (%s) — skipping",
                case.case_number_full, case.case_title,
            )
            result.errors.append(f"{case.case_number_full}: Form 204 not found")
            result.cases_skipped += 1
            continue

        s3.put_bytes(s3_key, pdf_bytes, content_type="application/pdf")
        logger.info(
            "Uploaded Form 204 for %s (%s) → %s (%d bytes)",
            case.case_number_full, case.case_title, s3_key, len(pdf_bytes),
        )
        result.cases_uploaded += 1

    # 5. Update last run timestamp
    _set_last_run_date(
        settings.supabase_url, settings.supabase_service_role_key,
        settings.supabase_http_timeout_sec, until,
    )

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
        "Intake complete: found=%d uploaded=%d skipped=%d errors=%d",
        result.cases_found, result.cases_uploaded, result.cases_skipped, len(result.errors),
    )
    if result.errors:
        for err in result.errors:
            logger.warning("  - %s", err)
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
