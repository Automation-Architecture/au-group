"""Form 204 retrieval — pluggable, cost-optimised source strategy.

Discovery (which new Chapter 11 cases exist) stays in ``intake.PacerClient``.
This module decides *where* to fetch each case's Form 204 ("List of Creditors
Who Have the 20 Largest Unsecured Claims") PDF, **cheapest source first**:

  1. ``RecapRetriever`` — Free Law Project's CourtListener/RECAP archive.
     FREE for any document already archived; one official, documented JSON API.
     Primary source.  Misses (doc not yet in the archive) return ``None`` so the
     strategy falls through.
  2. ``PacerCmecfRetriever`` — the existing direct CM/ECF fetch via the PACER
     session (``intake.PacerClient.download_form_204``).  Incurs PACER fees.
     Fallback for RECAP misses.  Still UNVERIFIED (see intake.py).

``CompositeRetriever`` tries them in order and returns the first hit, recording
which source paid off (for cost tracking in the daily report / logs).

A future ``RecapFetchRetriever`` would POST to ``/recap-fetch/`` to *purchase* a
not-yet-archived document through the operator's PACER account (paid, async).
Its interface slot is the same ``FormRetriever`` protocol; not implemented yet
because it needs a standard PACER account (open question Q1, see the discovery
doc).

Why not scrape the claims-agent sites (Kroll/Stretto/Epiq/…) directly?  A
2026-06-13 spike found their document downloads are reCAPTCHA-walled and the
metadata sits behind per-site bespoke SPAs — six brittle scrapers, exactly the
maintenance/ToS trap we set out to avoid.  See
``docs/architecture/pacer-data-source-discovery-2026-06-02.md``.

API contract (field names, call sequence, rate limits) is documented in
``docs/architecture/courtlistener-recap-api-reference.md``.  CourtListener REST
is rate-limited (5/min, 50/hr, 125/day authenticated) so RecapRetriever does at
most ONE search call per case on the happy path and only falls back to the
two-call docket-entries walk when the search slice has no confident match.

NOTE (verification status): RecapRetriever is built against the *documented*
CourtListener v4 contract but has not been exercised against the live API — that
needs a Free Law Project API token (CL_API_TOKEN).  The unit tests mock the
documented response shapes.  Identification from metadata alone is best-effort;
the downstream parse stage classifies the PDF and rejects a non-creditor-list,
so a mis-pick fails safe rather than corrupting Salesforce.  Mark the live
coverage check done once a token lands and a real case round-trips.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)

_CL_BASE = "https://www.courtlistener.com/api/rest/v4"
_CL_STORAGE = "https://storage.courtlistener.com"

# CourtListener's authenticated REST tier is 5/min, 50/hr. A daily intake batch
# fires several lookups back-to-back, so 429s are expected — back off and retry
# rather than treat a rate-limit as "not archived" (which would spuriously fall
# through to a PAID PACER fetch, defeating the free-first design). Module-level
# so tests can zero the delay. Base 2s × exp over 4 attempts ≈ 14s, enough to
# clear the rolling 5/min window.
_RECAP_MAX_ATTEMPTS = 4
_RECAP_RETRY_BASE_SEC = 2.0

# A Form 204 / top-20 (or the consolidated top-30 large multi-debtor cases file
# instead) is *defined* by the phrase "N largest [unsecured]".  Require it — the
# bare full creditor matrix ("List of Creditors" / "Creditor Matrix") does NOT
# say "largest" and must not match (it's a different, often huge document).
_FORM_204_POSITIVE = re.compile(
    r"\b(?:\d+|twenty|thirty)\s+largest\b|\blargest\s+unsecured\b",
    re.IGNORECASE,
)
# …but exclude docket entries that merely *reference* the list — motions,
# orders, notices, affidavits of service, etc. routinely contain "30 largest"
# in their title yet are not the list itself.
_FORM_204_NEGATIVE = re.compile(
    r"\b(motion|order|notice|affidavit|certificate|declaration|"
    r"hearing|agenda|objection|application|stipulation|response)\b",
    re.IGNORECASE,
)

# Extract the 'NN-NNNNN' docket-number core from a PCL caseNumberFull such as
# '2:23-bk-13359' or '1:26bk12345' → '23-13359' / '26-12345' for RECAP's
# docket_number filter.  RECAP stores the office-prefixed hyphenated form.
_DOCKET_NUM_RE = re.compile(r"(\d{2})-?bk-?(\d+)", re.IGNORECASE)


def recap_docket_number(case_number_full: str) -> str:
    """Normalise a PCL caseNumberFull to RECAP's 'YY-NNNNN' docket_number.

    Falls back to a trailing 'NN-NNNNN' match, else returns the input unchanged.
    The ``court`` filter is always supplied alongside this, and the docket
    lookup disambiguates multiple hits by debtor-name similarity, so a loose
    number widens rather than breaks the match.
    """
    m = _DOCKET_NUM_RE.search(case_number_full or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m2 = re.search(r"(\d{2}-\d+)", case_number_full or "")
    return m2.group(1) if m2 else (case_number_full or "")


# ---------------------------------------------------------------------------
# Shared types
# ---------------------------------------------------------------------------

@dataclass
class CaseRef:
    """The minimum a retriever needs, decoupled from intake.PacerCase.

    ``court_id`` is the CourtListener/PACER court id WITHOUT the PCL 'k' suffix
    (e.g. 'njb', 'nysb') — intake strips the suffix when building this.
    """
    court_id: str
    case_number_full: str
    debtor_name: str
    case_link: str = ""  # CM/ECF docket URL (used only by the PACER fallback)


@dataclass
class RetrievalResult:
    pdf: bytes
    source: str                       # 'recap' | 'pacer_cmecf' | ...
    document_number: str | None = None
    page_count: int | None = None
    cost_note: str = ""               # human note for logs/report ('free (archived)', 'PACER fees')


class FormRetriever(Protocol):
    def retrieve(self, case: CaseRef) -> RetrievalResult | None: ...


# ---------------------------------------------------------------------------
# Form 204 identification
# ---------------------------------------------------------------------------

def _doc_matches(doc: dict) -> bool:
    """True if a recap-document looks like a Form 204 / top-20|30 list itself.

    Requires the defining "N largest"/"largest unsecured" phrase AND rejects
    document-type noise (motions/orders/notices that merely cite the list).
    """
    text = f"{doc.get('description') or ''} {doc.get('short_description') or ''}"
    return bool(_FORM_204_POSITIVE.search(text)) and not _FORM_204_NEGATIVE.search(text)


def _doc_sort_key(doc: dict) -> tuple[int, int]:
    """Prefer the earliest-filed, shortest matching doc.

    Form 204 is filed with the petition (low document_number) and is short
    (1–3 pages).  Lower sorts first; missing/zero values sort last.
    """
    def _as_int(v: object, default: int) -> int:
        try:
            n = int(str(v).split(".")[0])
        except (TypeError, ValueError):
            return default
        return n if n > 0 else default

    return (_as_int(doc.get("document_number"), 10**9),
            _as_int(doc.get("page_count"), 10**9))


def _pick_form_204(docs: list[dict]) -> dict | None:
    """Return the best available Form-204 candidate, or None.

    Only considers docs that match the description patterns AND are present in
    the free archive (``is_available``) AND expose a ``filepath_local``.
    """
    candidates = [
        d for d in docs
        if _doc_matches(d) and d.get("is_available") and d.get("filepath_local")
    ]
    if not candidates:
        return None
    return sorted(candidates, key=_doc_sort_key)[0]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


# ---------------------------------------------------------------------------
# RECAP / CourtListener retriever (FREE archived reads)
# ---------------------------------------------------------------------------

class RecapRetriever:
    """Fetch a Form 204 from the CourtListener/RECAP archive (free if present).

    Call budget (CourtListener REST is 5/min): one Search call on the happy
    path; a docket-entries walk (reusing the docket id from the search result
    when available) only when the search slice has no confident match.  The PDF
    download hits storage.courtlistener.com directly and does NOT consume the
    REST budget or require auth.
    """

    def __init__(self, api_token: str, timeout: float = 30.0,
                 max_entry_pages: int = 3) -> None:
        self._token = api_token
        self._timeout = timeout
        self._max_entry_pages = max_entry_pages  # cap docket-entries pagination

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Token {self._token}", "Accept": "application/json"}

    def _get_json(self, client: httpx.Client, url: str, **kwargs) -> dict | None:
        """GET → JSON, backing off on 429/5xx, returning None on a real miss.

        429 (rate limit) and 5xx/network errors are retried with exponential
        backoff — a rate-limit must NOT be read as "not archived" (that would
        escalate to a paid PACER fetch). A 4xx other than 429, a non-JSON body,
        or exhausted retries return None so the caller falls through to the next
        (free) step or the paid fallback.
        """
        for attempt in range(1, _RECAP_MAX_ATTEMPTS + 1):
            try:
                resp = client.get(url, headers=self._headers(), **kwargs)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                code = exc.response.status_code
                if (code == 429 or 500 <= code < 600) and attempt < _RECAP_MAX_ATTEMPTS:
                    delay = _RECAP_RETRY_BASE_SEC * (2 ** (attempt - 1))
                    logger.warning("RECAP %d on %s — backing off %.0fs (attempt %d/%d)",
                                   code, url, delay, attempt, _RECAP_MAX_ATTEMPTS)
                    time.sleep(delay)
                    continue
                logger.warning("RECAP GET %s failed: %s", url, exc)
                return None
            except httpx.RequestError as exc:
                if attempt < _RECAP_MAX_ATTEMPTS:
                    delay = _RECAP_RETRY_BASE_SEC * (2 ** (attempt - 1))
                    logger.warning("RECAP network error on %s — backing off %.0fs (attempt %d/%d): %s",
                                   url, delay, attempt, _RECAP_MAX_ATTEMPTS, exc)
                    time.sleep(delay)
                    continue
                logger.warning("RECAP GET %s failed: %s", url, exc)
                return None
            except ValueError as exc:  # non-JSON 200 (maintenance/interstitial) — not transient
                logger.warning("RECAP non-JSON from %s: %s", url, exc)
                return None
        return None

    def retrieve(self, case: CaseRef) -> RetrievalResult | None:
        doc, docket_id = self._search(case)
        if doc is None:
            doc = self._walk_docket_entries(case, docket_id)
        if not doc:
            logger.info("RECAP: no archived Form 204 for %s (%s)",
                        case.case_number_full, case.debtor_name)
            return None

        pdf = self._download(doc["filepath_local"])
        if pdf is None:
            return None

        doc_num = doc.get("document_number")
        return RetrievalResult(
            pdf=pdf,
            source="recap",
            document_number=str(doc_num) if doc_num is not None else None,
            page_count=doc.get("page_count"),
            cost_note="free (RECAP archive)",
        )

    # -- step 1: one Search call (docket + nested recap_documents) ------------
    def _search(self, case: CaseRef) -> tuple[dict | None, int | None]:
        """Return (matched_doc | None, docket_id | None) from one Search call.

        ``docket_id`` is returned even on a no-match so the docket-entries
        fallback can reuse it instead of re-querying /dockets/.
        """
        params = {
            "type": "r",
            "court": case.court_id,
            "docket_number": recap_docket_number(case.case_number_full),
            "description": "largest",        # server-side narrow, aligned with the matcher
            "available_only": "on",
        }
        with httpx.Client(timeout=self._timeout) as client:
            data = self._get_json(client, f"{_CL_BASE}/search/", params=params)
        if not data:
            return None, None

        docket_id: int | None = None
        for result in (data.get("results") or []):
            if docket_id is None:
                docket_id = result.get("docket_id")
            picked = _pick_form_204(result.get("recap_documents") or [])
            if picked:
                return picked, docket_id
        # No confident match in the (≤3-doc) slice — caller walks the full docket
        # (covers the more_docs==True case where the 204 is beyond the slice).
        return None, docket_id

    # -- step 2 (fallback): docket-entries walk, earliest entries first -------
    def _walk_docket_entries(self, case: CaseRef, docket_id: int | None) -> dict | None:
        if docket_id is None:
            docket_id = self._find_docket_id(case)
        if docket_id is None:
            return None

        url: str | None = f"{_CL_BASE}/docket-entries/"
        # Form 204 is an early entry (filed with the petition) — scan ascending
        # so the capped page window covers it.
        params: dict | None = {"docket": docket_id, "order_by": "entry_number"}
        found: list[dict] = []
        pages = 0
        with httpx.Client(timeout=self._timeout) as client:
            while url and pages < self._max_entry_pages:
                data = self._get_json(client, url, params=params)
                if not data:
                    break
                for entry in (data.get("results") or []):
                    found.extend(entry.get("recap_documents") or [])
                url = data.get("next")   # absolute URL; its querystring carries the filters
                params = None
                pages += 1
        # Pick once across everything walked (global, not per-page).
        return _pick_form_204(found)

    def _find_docket_id(self, case: CaseRef) -> int | None:
        params = {"court": case.court_id,
                  "docket_number": recap_docket_number(case.case_number_full)}
        with httpx.Client(timeout=self._timeout) as client:
            data = self._get_json(client, f"{_CL_BASE}/dockets/", params=params)
        results = (data or {}).get("results") or []
        if not results:
            return None
        # docket_number is non-unique within a court; disambiguate by debtor name.
        want = _norm(case.debtor_name)
        if want:
            for r in results:
                if want in _norm(r.get("case_name", "")):
                    return r.get("id")
        return results[0].get("id")

    # -- download (public, no auth, off the REST budget) ----------------------
    def _download(self, filepath_local: str) -> bytes | None:
        url = f"{_CL_STORAGE}/{filepath_local.lstrip('/')}"
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(url, follow_redirects=True)
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("RECAP PDF download failed from %s: %s", url, exc)
            return None
        ctype = resp.headers.get("content-type", "").lower()
        if "pdf" not in ctype and "octet-stream" not in ctype:
            logger.warning("RECAP download is not a PDF (content-type=%s): %s", ctype, url)
            return None
        if not resp.content:
            logger.warning("RECAP download was empty (0 bytes): %s", url)
            return None
        return resp.content


# ---------------------------------------------------------------------------
# PACER CM/ECF retriever (paid fallback — wraps the existing intake client)
# ---------------------------------------------------------------------------

class PacerCmecfRetriever:
    """Fallback: direct CM/ECF fetch via an authenticated intake.PacerClient.

    Injected (not imported) to avoid a circular dependency with intake.py.
    ``pacer_client`` must expose ``download_form_204(case_link, token) -> bytes | None``.
    Incurs PACER per-page fees; still UNVERIFIED (see intake.download_form_204).
    """

    def __init__(self, pacer_client: object, token: str) -> None:
        self._pacer = pacer_client
        self._token = token

    def retrieve(self, case: CaseRef) -> RetrievalResult | None:
        if not case.case_link:
            return None
        pdf = self._pacer.download_form_204(case.case_link, self._token)  # type: ignore[attr-defined]
        if pdf is None:
            return None
        return RetrievalResult(pdf=pdf, source="pacer_cmecf", cost_note="PACER fees")


# ---------------------------------------------------------------------------
# Strategy: try sources cheapest-first
# ---------------------------------------------------------------------------

class CompositeRetriever:
    """Try each retriever in order; return the first non-None result.

    A retriever raising is logged and treated as a miss so one failing source
    never blocks a cheaper/dearer alternative.
    """

    def __init__(self, retrievers: list[FormRetriever]) -> None:
        self._retrievers = retrievers

    def retrieve(self, case: CaseRef) -> RetrievalResult | None:
        for r in self._retrievers:
            name = type(r).__name__
            try:
                result = r.retrieve(case)
            except Exception as exc:  # noqa: BLE001 — one bad source must not kill the rest
                logger.warning("%s raised for %s: %s", name, case.case_number_full, exc)
                continue
            if result is not None:
                logger.info("Form 204 for %s via %s (%s)",
                            case.case_number_full, result.source, result.cost_note)
                return result
        return None
