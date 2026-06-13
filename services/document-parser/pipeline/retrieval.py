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
two-call docket-entries walk when the search slice is incomplete.

NOTE (verification status): RecapRetriever is built against the *documented*
CourtListener v4 contract but has not been exercised against the live API — that
needs a Free Law Project API token (CL_API_TOKEN).  The unit tests mock the
documented response shapes.  Mark the live coverage check done once a token
lands and a real case round-trips.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)

_CL_BASE = "https://www.courtlistener.com/api/rest/v4"
_CL_STORAGE = "https://storage.courtlistener.com"

# Document-description patterns that identify a Form 204 / top-20 (or the
# consolidated top-30 large multi-debtor cases file instead).  Matched against
# a recap-document's ``description`` (REST) or ``short_description`` (Search).
_FORM_204_PATTERNS = re.compile(
    r"20\s+largest|30\s+largest|largest\s+unsecured|"
    r"creditors\s+who\s+have|creditors\s+holding|list\s+of\s+(?:the\s+)?creditors",
    re.IGNORECASE,
)

# Extract the 'NN-NNNNN' docket-number core from a PCL caseNumberFull such as
# '2:23-bk-13359' or '1:26bk12345' → '23-13359' / '26-12345' for RECAP's
# docket_number filter.  RECAP stores the office-prefixed hyphenated form.
_DOCKET_NUM_RE = re.compile(r"(\d{2})-?bk-?(\d+)", re.IGNORECASE)


def recap_docket_number(case_number_full: str) -> str:
    """Normalise a PCL caseNumberFull to RECAP's 'YY-NNNNN' docket_number.

    Falls back to the trailing 'NN-NNNNN' if the 'bk' form isn't present, else
    returns the input unchanged (caller still passes ``court`` so a loose
    docket_number just widens the match, which we then disambiguate by name).
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
    """True if a recap-document looks like a Form 204 / top-20|30 list."""
    text = f"{doc.get('description') or ''} {doc.get('short_description') or ''}"
    return bool(_FORM_204_PATTERNS.search(text))


def _doc_sort_key(doc: dict) -> tuple[int, int]:
    """Prefer the earliest-filed, shortest matching doc.

    Form 204 is filed with the petition (low document_number) and is short
    (1–3 pages).  Lower sorts first; missing values sort last.
    """
    def _as_int(v: object, default: int) -> int:
        try:
            return int(str(v).split(".")[0])
        except (TypeError, ValueError):
            return default

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


# ---------------------------------------------------------------------------
# RECAP / CourtListener retriever (FREE archived reads)
# ---------------------------------------------------------------------------

class RecapRetriever:
    """Fetch a Form 204 from the CourtListener/RECAP archive (free if present).

    Call budget (CourtListener REST is 5/min): one Search call on the happy
    path; a 2-call dockets→docket-entries walk only when the search slice is
    incomplete.  The PDF download hits storage.courtlistener.com directly and
    does NOT consume the REST budget or require auth.
    """

    def __init__(self, api_token: str, timeout: float = 30.0,
                 max_entry_pages: int = 3) -> None:
        self._token = api_token
        self._timeout = timeout
        self._max_entry_pages = max_entry_pages  # cap docket-entries pagination

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Token {self._token}", "Accept": "application/json"}

    def retrieve(self, case: CaseRef) -> RetrievalResult | None:
        doc = self._search_for_doc(case) or self._walk_docket_entries(case)
        if not doc:
            logger.info("RECAP: no archived Form 204 for %s (%s)",
                        case.case_number_full, case.debtor_name)
            return None

        pdf = self._download(doc["filepath_local"])
        if pdf is None:
            return None

        return RetrievalResult(
            pdf=pdf,
            source="recap",
            document_number=str(doc.get("document_number")) if doc.get("document_number") is not None else None,
            page_count=doc.get("page_count"),
            cost_note="free (RECAP archive)",
        )

    # -- step 1: one Search call (returns docket + nested recap_documents) -----
    def _search_for_doc(self, case: CaseRef) -> dict | None:
        params = {
            "type": "r",
            "court": case.court_id,
            "docket_number": recap_docket_number(case.case_number_full),
            "description": "largest unsecured",  # server-side narrow to the 204
            "available_only": "on",
        }
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(f"{_CL_BASE}/search/", headers=self._headers(), params=params)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            logger.warning("RECAP search failed for %s: %s", case.case_number_full, exc)
            return None

        for result in (data.get("results") or []):
            docs = result.get("recap_documents") or []
            picked = _pick_form_204(docs)
            if picked:
                return picked
        return None

    # -- step 2 (fallback): dockets → docket-entries walk ---------------------
    def _walk_docket_entries(self, case: CaseRef) -> dict | None:
        docket_id = self._find_docket_id(case)
        if docket_id is None:
            return None

        url: str | None = f"{_CL_BASE}/docket-entries/"
        params: dict | None = {"docket": docket_id}
        pages = 0
        try:
            with httpx.Client(timeout=self._timeout) as client:
                while url and pages < self._max_entry_pages:
                    resp = client.get(url, headers=self._headers(), params=params)
                    resp.raise_for_status()
                    data = resp.json()
                    docs: list[dict] = []
                    for entry in (data.get("results") or []):
                        docs.extend(entry.get("recap_documents") or [])
                    picked = _pick_form_204(docs)
                    if picked:
                        return picked
                    url = data.get("next")  # absolute URL; params already encoded in it
                    params = None
                    pages += 1
        except httpx.HTTPError as exc:
            logger.warning("RECAP docket-entries walk failed for %s: %s",
                           case.case_number_full, exc)
            return None
        return None

    def _find_docket_id(self, case: CaseRef) -> int | None:
        params = {"court": case.court_id,
                  "docket_number": recap_docket_number(case.case_number_full)}
        try:
            with httpx.Client(timeout=self._timeout) as client:
                resp = client.get(f"{_CL_BASE}/dockets/", headers=self._headers(), params=params)
                resp.raise_for_status()
                results = resp.json().get("results") or []
        except httpx.HTTPError as exc:
            logger.warning("RECAP docket lookup failed for %s: %s", case.case_number_full, exc)
            return None
        if not results:
            return None
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
