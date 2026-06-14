"""Case discovery — find new Chapter 11 filings to feed the pipeline.

Two sources, mirroring the retrieval split (see pipeline/retrieval.py):

  - ``CourtListenerDiscoverer`` — Free Law Project's CourtListener Search API.
    Free, uses the token already wired for RECAP, and needs NO standard PACER
    account. This is the OD-8 resolution: discover via CourtListener now, add
    authoritative PACER PCL discovery later when a standard PACER account exists.
  - PACER PCL (the authoritative same-day index) stays in
    ``intake.PacerClient.search_new_cases`` — used when PACER credentials are
    configured; not required for the pipeline to produce cases.

CourtListener discovery contract (verified 2026-06-14):
  GET /api/rest/v4/search/?type=r&court=<space-joined ids>&q=chapter:11
      &filed_after=YYYY-MM-DD&filed_before=YYYY-MM-DD&order_by=dateFiled desc
  - Chapter is filtered SERVER-SIDE via the q=chapter:N operator (the bare
    ?chapter= param and the /dockets/ data endpoint do NOT support it).
  - Result fields (mixed casing): docket_id, caseName, docketNumber, court_id,
    dateFiled, chapter.
  - Cursor pagination via ``next``; page_size capped at 20.
  - Auth REST limit is 5000/hr, but bursts can 429 → back off (handled here).

Known coverage caveat (documented, not yet mitigated): ~13% of brand-new
filings arrive with a blank ``chapter`` and are therefore missed by q=chapter:11
until CourtListener enriches them. A follow-up can add a no-filter sweep that
captures blank-chapter dockets and re-checks their chapter on a later pass.
CourtListener is RSS-fed and same-day-ish for the target bankruptcy courts, but
coverage is not the authoritative PACER index — hence "add PACER later".
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date

import httpx

logger = logging.getLogger(__name__)

_CL_BASE = "https://www.courtlistener.com/api/rest/v4"

# Burst 429s happen even under the 5000/hr ceiling — back off and retry.
_DISCOVERY_MAX_ATTEMPTS = 4
_DISCOVERY_RETRY_BASE_SEC = 2.0


@dataclass
class DiscoveredCase:
    """A discovered filing. Field names match intake.PacerCase so the intake
    per-case loop is source-agnostic. ``court_id`` is the bare court id (no PCL
    'k' suffix), e.g. 'njb'."""
    court_id: str
    case_number_full: str
    case_title: str
    date_filed: str          # 'YYYY-MM-DD'
    chapter: str = "11"
    case_link: str = ""      # CourtListener docket URL (informational)


class CourtListenerDiscoverer:
    """Discover new Chapter 11 dockets via the CourtListener Search API."""

    def __init__(self, api_token: str, timeout: float = 30.0, max_pages: int = 10) -> None:
        self._token = api_token
        self._timeout = timeout
        self._max_pages = max_pages  # 20 results/page → cap total per run

    def _get(self, client: httpx.Client, url: str, params: dict | None) -> dict | None:
        """GET → JSON with 429/5xx/network backoff; None on non-retryable failure."""
        headers = {"Authorization": f"Token {self._token}", "Accept": "application/json"}
        for attempt in range(1, _DISCOVERY_MAX_ATTEMPTS + 1):
            try:
                resp = client.get(url, headers=headers, params=params)
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as exc:
                code = exc.response.status_code
                if (code == 429 or 500 <= code < 600) and attempt < _DISCOVERY_MAX_ATTEMPTS:
                    delay = _DISCOVERY_RETRY_BASE_SEC * (2 ** (attempt - 1))
                    logger.warning("CourtListener %d on discovery — backing off %.0fs (attempt %d/%d)",
                                   code, delay, attempt, _DISCOVERY_MAX_ATTEMPTS)
                    time.sleep(delay)
                    continue
                logger.warning("CourtListener discovery GET failed: %s", exc)
                return None
            except httpx.RequestError as exc:
                if attempt < _DISCOVERY_MAX_ATTEMPTS:
                    time.sleep(_DISCOVERY_RETRY_BASE_SEC * (2 ** (attempt - 1)))
                    continue
                logger.warning("CourtListener discovery network error: %s", exc)
                return None
            except ValueError as exc:
                logger.warning("CourtListener discovery non-JSON response: %s", exc)
                return None
        return None

    def discover(self, court_ids: list[str], date_from: date, date_to: date,
                 chapter: int = 11) -> list[DiscoveredCase]:
        """Return new Chapter-`chapter` dockets across `court_ids` in the window.

        Server-side chapter filter via q=chapter:N. Future-dated sentinel rows
        (CourtListener has bogus entries like dateFiled=2029) are dropped.
        """
        if not court_ids:
            return []
        until_iso = date_to.isoformat()
        params: dict | None = {
            "type": "r",
            "court": " ".join(court_ids),
            "q": f"chapter:{chapter}",
            "filed_after": date_from.isoformat(),
            "filed_before": until_iso,
            "order_by": "dateFiled desc",
        }
        cases: list[DiscoveredCase] = []
        url: str | None = f"{_CL_BASE}/search/"
        pages = 0
        with httpx.Client(timeout=self._timeout) as client:
            while url and pages < self._max_pages:
                data = self._get(client, url, params)
                if not data:
                    break
                for r in (data.get("results") or []):
                    df = r.get("dateFiled") or ""
                    docket_number = r.get("docketNumber")
                    if not docket_number:
                        continue
                    if df and df > until_iso:
                        continue  # future-dated sentinel row — skip
                    cases.append(DiscoveredCase(
                        court_id=r.get("court_id", ""),
                        case_number_full=str(docket_number),
                        case_title=r.get("caseName", "") or "",
                        date_filed=df,
                        chapter=str(r.get("chapter") or chapter),
                        case_link=r.get("docket_absolute_url", "") or "",
                    ))
                url = data.get("next")   # absolute cursor URL; params already encoded in it
                params = None
                pages += 1
        logger.info("CourtListener discovery: %d Chapter %s cases across %d courts (%s→%s)",
                    len(cases), chapter, len(court_ids), date_from, date_to)
        return cases
