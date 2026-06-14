"""Pipeline ZoomInfo enrichment stage — WP-08 (KD-67).

The worker dispatches ``zoom_info_enrich`` jobs here (gated by ``SKIP_ENRICH``;
the worker requeues while that flag is set, so the stage never runs until the
operator turns it on).  For each job — one per bankruptcy — this stage enriches
every **company** creditor of that filing via the ZoomInfo GTM Data API:

  1. Enrich the company (ZoomInfo ``POST /data/v1/companies/enrich``) by name +
     state — one creditor per call (the batch endpoint returns records in an
     order you can't safely map back to inputs; per filing it's ≤20 creditors,
     so batching buys nothing and mis-assigning a tier is the failure that
     matters).
  2. Classify the tier from revenue/employee count → ``creditors.company_tier``
     (smallint 1=Enterprise, 2=Mid-Market, 3=SMB).
  3. On a confident match, persist the ZoomInfo company id + canonical name and
     write a company-level ``zoom_info_contacts`` row (contact fields NULL —
     decision-maker contacts are manual/Phase 2).
  4. After the loop, enqueue ``salesforce_push`` once (leads flow to SF whether
     or not ZoomInfo matched — salesforce.py treats tier/zoominfo as optional).

Auth is OAuth 2.0 Client Credentials (the GTM API; see
``Resources/zoominfo-api/guides/client-credentials-flow.md``).

NOTE (verification status — BLOCKED on ZoomInfo access): built against the
documented GTM contract and unit-tested with an injected fake client.  The
ZoomInfo account is not yet API-enabled (KD-53) — the stored DevPortal secret
fails ``invalid_client``.  Operationally gated by ``SKIP_ENRICH=true``; the
cred-guard is a safety net behind it.  FIRST-LIVE-CALL CHECKLIST (do before
trusting any tier in production):
  - confirm the ``revenue`` unit — the schema says "in 1000's" ($100M → 100000);
    a wrong unit misclassifies UPWARD via the OR rule. Verify against a known
    company, then keep/adjust _REVENUE_*_K.
  - confirm ``matchStatus`` enum values actually returned (FULL_MATCH / NO_MATCH
    / any partial) and that ``ZOOMINFO_MATCH_STATUS`` is the right floor.
  - confirm ``employeeCount`` is the populated field (vs ``employeeRange``).
"""

from __future__ import annotations

import base64
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from pipeline.alerts import send_error_alert
from pipeline.settings import PipelineSettings, get_pipeline_settings

logger = logging.getLogger(__name__)

# Tier thresholds. revenue is ZoomInfo's "revenue" field, documented as
# thousands of USD ($100M → 100000); employees is "employeeCount". Either signal
# can promote a tier (FR-4.2 OR rule). One-line-flippable if the unit differs.
_REVENUE_ENTERPRISE_K = 1_000_000   # $1B
_REVENUE_MIDMARKET_K = 100_000      # $100M
_EMP_ENTERPRISE = 5_000
_EMP_MIDMARKET = 500

_OUTPUT_FIELDS = ["id", "name", "revenue", "employeeCount"]

# Transient-retry policy (module-level so tests can zero the delay).
_RETRY_MAX_ATTEMPTS = 3
_RETRY_BASE_SEC = 1.0


class _FatalEnrichError(RuntimeError):
    """Non-retryable enrichment failure (missing creds, auth, config)."""


# ---------------------------------------------------------------------------
# Tier classification
# ---------------------------------------------------------------------------

def _classify_tier(revenue_k: Any, employees: Any) -> int | None:
    """1=Enterprise, 2=Mid-Market, 3=SMB, or None when neither signal is present."""
    rev = revenue_k if isinstance(revenue_k, (int, float)) and not isinstance(revenue_k, bool) else None
    emp = employees if isinstance(employees, int) and not isinstance(employees, bool) else None
    if rev is None and emp is None:
        return None
    if (rev is not None and rev >= _REVENUE_ENTERPRISE_K) or (emp is not None and emp >= _EMP_ENTERPRISE):
        return 1
    if (rev is not None and rev >= _REVENUE_MIDMARKET_K) or (emp is not None and emp >= _EMP_MIDMARKET):
        return 2
    return 3


def _is_transient(exc: Exception) -> bool:
    """429/5xx (or a network error) is worth retrying."""
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code == 429 or 500 <= code < 600
    return isinstance(exc, httpx.RequestError)


def _retry(fn, *args, **kwargs):
    """Call fn with exponential backoff on transient errors (429/5xx/network)."""
    last: Exception | None = None
    for attempt in range(1, _RETRY_MAX_ATTEMPTS + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — classify transient vs fatal
            last = exc
            if not _is_transient(exc) or attempt == _RETRY_MAX_ATTEMPTS:
                raise
            delay = _RETRY_BASE_SEC * (2 ** (attempt - 1))
            logger.warning("ZoomInfo transient error (attempt %d/%d): %s — retrying in %.0fs",
                           attempt, _RETRY_MAX_ATTEMPTS, exc, delay)
            time.sleep(delay)
    raise last  # unreachable


# ---------------------------------------------------------------------------
# ZoomInfo GTM client (OAuth client-credentials + company enrich)
# ---------------------------------------------------------------------------

@dataclass
class EnrichResult:
    matched: bool
    company_id: str | None = None
    canonical_name: str | None = None
    revenue: float | None = None
    employee_count: int | None = None


class ZoomInfoClient:
    """Minimal ZoomInfo GTM client: token via client-credentials, company enrich.

    Constructed via ``build_zoominfo_client`` (which fetches the token).  Inject
    a duck-typed stand-in in tests (only ``enrich_company`` is used downstream).
    """

    def __init__(self, token: str, base_url: str, timeout: float, match_floor: str) -> None:
        self._token = token
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._match_floor = match_floor

    def enrich_company(self, name: str, state: str | None) -> EnrichResult:
        match_input: dict[str, Any] = {"companyName": name}
        if state:
            match_input["state"] = state
        body = {"data": {"type": "CompanyEnrich", "attributes": {
            "matchCompanyInput": [match_input], "outputFields": _OUTPUT_FIELDS}}}

        def _call() -> dict:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.post(
                    f"{self._base}/data/v1/companies/enrich",
                    headers={"Authorization": f"Bearer {self._token}",
                             "Content-Type": "application/vnd.api+json",
                             "Accept": "application/vnd.api+json"},
                    json=body,
                )
                resp.raise_for_status()
                return resp.json()

        data = (_retry(_call).get("data") or [])
        if not data:
            return EnrichResult(matched=False)
        record = data[0]
        attrs = record.get("attributes") or {}
        status = (record.get("meta") or {}).get("matchStatus", "")
        if status != self._match_floor:
            logger.info("ZoomInfo match below floor (%s) for %r", status, name)
            return EnrichResult(matched=False)
        return EnrichResult(
            matched=True,
            company_id=str(record.get("id")) if record.get("id") is not None else None,
            canonical_name=attrs.get("name"),
            revenue=attrs.get("revenue"),
            employee_count=attrs.get("employeeCount"),
        )


def build_zoominfo_client(settings: PipelineSettings) -> ZoomInfoClient:
    """Fetch an OAuth client-credentials token and return a ready ZoomInfoClient."""
    base = settings.zoominfo_base_url.rstrip("/")
    basic = base64.b64encode(
        f"{settings.zoominfo_client_id}:{settings.zoominfo_client_secret}".encode()
    ).decode()
    try:
        with httpx.Client(timeout=settings.zoominfo_timeout_sec) as client:
            resp = client.post(
                f"{base}/oauth/v1/token",
                headers={"Authorization": f"Basic {basic}",
                         "Content-Type": "application/x-www-form-urlencoded",
                         "Accept": "application/json"},
                data={"grant_type": "client_credentials"},
            )
            resp.raise_for_status()
            token = resp.json().get("access_token")
    except httpx.HTTPError as exc:
        raise _FatalEnrichError(f"ZoomInfo token request failed: {exc}") from exc
    if not token:
        raise _FatalEnrichError("ZoomInfo token response had no access_token")
    return ZoomInfoClient(token, base, settings.zoominfo_timeout_sec, settings.zoominfo_match_status)


# ---------------------------------------------------------------------------
# Supabase reads / writes (httpx — same idiom as parse.py / salesforce.py)
# ---------------------------------------------------------------------------

def _supabase_headers(key: str) -> dict[str, str]:
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def _list_company_creditors(bankruptcy_id: str, url: str, key: str, t: float) -> list[dict[str, Any]]:
    with httpx.Client(timeout=t) as client:
        resp = client.post(
            f"{url.rstrip('/')}/rest/v1/rpc/au_group_list_company_creditors",
            headers=_supabase_headers(key),
            json={"p_bankruptcy_id": bankruptcy_id},
        )
        resp.raise_for_status()
    rows = resp.json()
    return rows if isinstance(rows, list) else []


def _patch_creditor(creditor_id: str, fields: dict[str, Any], url: str, key: str, t: float) -> None:
    if not fields:
        return
    with httpx.Client(timeout=t) as client:
        resp = client.patch(
            f"{url.rstrip('/')}/rest/v1/creditors",
            headers={**_supabase_headers(key), "Prefer": "return=minimal"},
            params={"id": f"eq.{creditor_id}"},
            json=fields,
        )
        resp.raise_for_status()


def _set_zoominfo_id(creditor_id: str, company_id: str, url: str, key: str, t: float) -> None:
    with httpx.Client(timeout=t) as client:
        resp = client.post(
            f"{url.rstrip('/')}/rest/v1/rpc/au_group_set_creditor_zoominfo_company_id",
            headers=_supabase_headers(key),
            json={"p_creditor_id": creditor_id, "p_company_id": company_id},
        )
        resp.raise_for_status()


def _upsert_contact(creditor_id: str, full_name: str, revenue: Any, employees: Any,
                    url: str, key: str, t: float) -> None:
    """Write the company-level zoom_info_contacts row, idempotently.

    zoom_info_contacts has no unique on creditor_id and enrich can re-run for the
    same creditor (re-processed case, partial-failure re-enqueue), so a bare
    INSERT would duplicate the row — delete-then-insert keeps it single.
    full_name is NOT NULL, so the canonical company name sits there; the actual
    contact fields (title/email/phone) stay NULL (Phase 2). Pipeline status keys
    "ZoomInfo Enriched" on row existence, not on full_name content.
    """
    with httpx.Client(timeout=t) as client:
        delete = client.delete(
            f"{url.rstrip('/')}/rest/v1/zoom_info_contacts",
            headers={**_supabase_headers(key), "Prefer": "return=minimal"},
            params={"creditor_id": f"eq.{creditor_id}"},
        )
        delete.raise_for_status()
        row: dict[str, Any] = {"creditor_id": creditor_id, "full_name": full_name[:255]}
        if isinstance(revenue, (int, float)) and not isinstance(revenue, bool):
            row["company_revenue"] = revenue
        if isinstance(employees, int) and not isinstance(employees, bool):
            row["company_employee_count"] = employees
        insert = client.post(
            f"{url.rstrip('/')}/rest/v1/zoom_info_contacts",
            headers={**_supabase_headers(key), "Prefer": "return=minimal"},
            json=row,
        )
        insert.raise_for_status()


def _enqueue_salesforce_push(bankruptcy_id: str, url: str, key: str, t: float) -> None:
    """Enqueue salesforce_push. No-ops if already queued/running."""
    with httpx.Client(timeout=t) as client:
        resp = client.post(
            f"{url.rstrip('/')}/rest/v1/rpc/au_group_enqueue_job",
            headers=_supabase_headers(key),
            json={"p_bankruptcy_id": bankruptcy_id, "p_job_type": "salesforce_push"},
        )
        resp.raise_for_status()


# ---------------------------------------------------------------------------
# Enricher
# ---------------------------------------------------------------------------

@dataclass
class EnrichSummary:
    enriched: int = 0
    no_match: int = 0
    failed: list[str] = field(default_factory=list)


class Enricher:
    """Enriches one filing's creditors via an injected ZoomInfo client."""

    def __init__(self, zi: Any, supabase_url: str, supabase_key: str, timeout: float) -> None:
        self._zi = zi
        self._url = supabase_url
        self._key = supabase_key
        self._t = timeout

    def _enrich_creditor(self, creditor: dict[str, Any]) -> bool:
        """Enrich + persist one creditor. Returns True if matched, False on no-match."""
        cid = creditor["creditor_id"]
        name = (creditor.get("normalized_name") or creditor.get("creditor_name") or "").strip()
        if not name:
            return False
        result: EnrichResult = self._zi.enrich_company(name, (creditor.get("creditor_state") or "").strip() or None)
        if not result.matched:
            return False  # NO_MATCH / below floor → write nothing, leave normalized_name as-is

        patch: dict[str, Any] = {}
        tier = _classify_tier(result.revenue, result.employee_count)
        if tier is not None:
            patch["company_tier"] = tier
        if result.canonical_name:
            patch["normalized_name"] = result.canonical_name  # ZoomInfo canonical (FR-4.2)
        _patch_creditor(cid, patch, self._url, self._key, self._t)

        if result.company_id:
            _set_zoominfo_id(cid, result.company_id, self._url, self._key, self._t)

        _upsert_contact(cid, result.canonical_name or name, result.revenue, result.employee_count,
                        self._url, self._key, self._t)
        return True

    def enrich_bankruptcy(self, creditors: list[dict[str, Any]]) -> EnrichSummary:
        summary = EnrichSummary()
        for creditor in creditors:
            cid = str(creditor.get("creditor_id", "?"))
            try:
                if self._enrich_creditor(creditor):
                    summary.enriched += 1
                else:
                    summary.no_match += 1
            except Exception as exc:  # noqa: BLE001 — isolate one creditor's failure
                logger.error("Creditor %s enrichment failed: %s", cid, exc)
                summary.failed.append(cid)
        return summary


# ---------------------------------------------------------------------------
# Worker entry point
# ---------------------------------------------------------------------------

def process_job(job: dict[str, Any]) -> None:
    """Process one zoom_info_enrich job. Called by worker._dispatch.

    Normal return → worker marks the job completed (and salesforce_push is queued).
    _FatalEnrichError / RuntimeError → worker marks failed + alerts.
    """
    settings = get_pipeline_settings()
    sb_url, sb_key, sb_t = settings.supabase_url, settings.supabase_service_role_key, settings.supabase_http_timeout_sec

    job_id = str(job.get("id", "?"))
    bankruptcy_id = job.get("bankruptcy_id")
    if not bankruptcy_id:
        raise _FatalEnrichError(f"zoom_info_enrich job {job_id} has no bankruptcy_id")

    # Guard: SKIP_ENRICH is the operational gate (the worker requeues while it is
    # set). If enrich is enabled but creds are absent that is a misconfiguration —
    # fail loudly (→ "Enrichment Failed" status + alert) rather than silently
    # marking the filing enriched.
    if not (settings.zoominfo_client_id and settings.zoominfo_client_secret):
        raise _FatalEnrichError("ZoomInfo credentials not set (ZOOMINFO_CLIENT_ID/SECRET)")

    creditors = _list_company_creditors(str(bankruptcy_id), sb_url, sb_key, sb_t)
    if not creditors:
        logger.info("No company creditors for %s — nothing to enrich", bankruptcy_id)
        return  # worker completes the job

    zi = build_zoominfo_client(settings)  # raises _FatalEnrichError on auth failure
    summary = Enricher(zi, sb_url, sb_key, sb_t).enrich_bankruptcy(creditors)

    # Leads flow to Salesforce whether or not ZoomInfo matched (tier is optional
    # downstream) — enqueue once, after the loop.
    _enqueue_salesforce_push(str(bankruptcy_id), sb_url, sb_key, sb_t)

    logger.info("zoom_info_enrich for %s: enriched=%d no_match=%d failed=%d — enqueued salesforce_push",
                bankruptcy_id, summary.enriched, summary.no_match, len(summary.failed))

    if summary.failed:
        send_error_alert(
            stage="enrich.py — partial enrichment",
            error=f"{bankruptcy_id}: {len(summary.failed)} creditor(s) failed enrichment: {summary.failed}",
            bankruptcy_id=str(bankruptcy_id),
            bot_token=settings.slack_bot_token,
            channel_id=settings.slack_channel_id,
        )
    return  # worker marks job completed
