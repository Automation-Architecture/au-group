"""BKwire CSV ingest — creditor rows without PACER, RECAP, OCR or parsing.

BKwire is a commercial bankruptcy feed the client is evaluating as a PACER
replacement (Keith, 2026-08-18). Its daily export is the Form 204 *output*: one
row per creditor-claim, already extracted. That removes the whole discovery →
Form 204 retrieval → OCR → parse chain — the part of this pipeline that has
never worked in production — and feeds the existing enrich → Salesforce → daily
report stages directly.

Export shape (verified against a real 2026-08-04 export of 100 rows):

    Date Added,Date Filed,Impacted Business,BKwire Zone,City,State,Case Number,
    Corporate Bankruptcy,Loss

  Impacted Business    the CREDITOR (this is the lead)
  Corporate Bankruptcy the DEBTOR that filed
  Loss                 claim amount, formatted ("$3,524")
  City/State           the CREDITOR's location, NOT the debtor's court
  BKwire Zone          9-value industry taxonomy
  Case Number          '7:2026bk70239' — the leading digit is the office /
                       division, NOT the chapter. Do not read '7:' as Chapter 7.

WHAT THE FEED DOES NOT CONTAIN, and what this module does about it
------------------------------------------------------------------
``bankruptcies`` requires court_district, state and chapter_type NOT NULL, and
BKwire supplies none of them:

  * court_district → the ``_COURT_DISTRICT_SENTINEL`` below, which records the
    provenance instead of inventing a district.
  * state (the DEBTOR's) → ``bkwire_unknown_state`` ('XX'). The creditor's own
    state travels in the address, which is what the report actually groups by
    (``au_group_parse_creditor_state`` reads it back out), so the sentinel only
    surfaces for rows whose creditor state is unusable.
  * chapter_type → ``bkwire_chapter_type``, default ``'unknown'`` (enum member
    added in migration 20260818220000). The feed carries no chapter and a
    524-row day is far above business Chapter 11 volume, so it is mixed-chapter;
    writing '11' would have been a fabricated value in a column other code is
    entitled to trust. Nothing filters on chapter_type today, so 'unknown' costs
    nothing downstream. Override only if the feed is ever known to be
    single-chapter.

Deliberately NOT automated here: fetching the file. The site caps downloads at
100 rows while a day held 524, and whether there is an API, a full export, or
only manual downloads is an open question with the vendor. This module ingests
a file that already exists; a fetcher can be added behind ``load_rows`` once the
answer lands (and only after the ToS position on automated access is settled).
"""

from __future__ import annotations

import csv
import io
import logging
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

import httpx

from pipeline.settings import PipelineSettings, get_pipeline_settings

logger = logging.getLogger(__name__)

# Provenance marker in the NOT NULL court_district column — BKwire gives no court.
_COURT_DISTRICT_SENTINEL = "BKWIRE"

REQUIRED_COLUMNS = (
    "Date Filed",
    "Impacted Business",
    "City",
    "State",
    "Case Number",
    "Corporate Bankruptcy",
    "Loss",
)

# Structured vendor data, not OCR — but not independently verified either.
_BKWIRE_CONFIDENCE = Decimal("0.95")

_STATE_RE = re.compile(r"^[A-Za-z]{2}$")


class BkwireFormatError(ValueError):
    """The file is not a BKwire export (missing required columns)."""


@dataclass
class BkwireRow:
    date_filed: str
    creditor: str
    debtor: str
    case_number: str
    city: str
    state: str | None          # None when unusable ('see petition', blank, …)
    claim_amount: Decimal | None
    zone: str = ""
    line_number: int = 0


@dataclass
class CaseGroup:
    case_number: str
    debtor: str
    date_filed: str
    creditors: list[dict] = field(default_factory=list)


@dataclass
class BkwireIngestResult:
    rows_read: int = 0
    rows_skipped: int = 0
    cases: int = 0
    creditors_merged: int = 0
    claims_combined: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Pure parsing / normalisation
# ---------------------------------------------------------------------------

def parse_loss(raw: str | None) -> Decimal | None:
    """'$3,524' → Decimal('3524'). None when absent or unparseable.

    Never raises: a malformed amount costs one field, not the row — the creditor
    name is what makes the lead, and a null claim is honest about not knowing.
    """
    if not raw:
        return None
    cleaned = re.sub(r"[^0-9.\-]", "", raw)
    if not cleaned or cleaned in {"-", ".", "-."}:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def normalize_state(raw: str | None) -> str | None:
    """Two-letter state, upper-cased; None for anything else.

    The real export contains ``State`` values such as 'see petition', so this
    must reject rather than propagate junk into a varchar(2) column.
    """
    value = (raw or "").strip()
    return value.upper() if _STATE_RE.match(value) else None


def format_address(city: str, state: str | None) -> str | None:
    """'Edinburg', 'TX' → 'Edinburg, TX'.

    The creditor's location lives in ``creditors.address``; the report reads it
    back with au_group_parse_creditor_state, so the ', ST' suffix matters.
    """
    city = (city or "").strip()
    if city and state:
        return f"{city}, {state}"
    return city or state or None


def parse_csv(text: str) -> tuple[list[BkwireRow], list[str]]:
    """Parse a BKwire export into rows + human-readable warnings.

    Raises BkwireFormatError if the header is not a BKwire export — better to
    fail loudly than to ingest an unrelated CSV as creditor leads.
    """
    reader = csv.DictReader(io.StringIO(text))
    header = reader.fieldnames or []
    missing = [c for c in REQUIRED_COLUMNS if c not in header]
    if missing:
        raise BkwireFormatError(
            f"not a BKwire export — missing column(s): {', '.join(missing)}; got {header}"
        )

    rows: list[BkwireRow] = []
    warnings: list[str] = []
    for line_number, raw in enumerate(reader, start=2):  # 1 is the header
        creditor = (raw.get("Impacted Business") or "").strip()
        case_number = (raw.get("Case Number") or "").strip()
        debtor = (raw.get("Corporate Bankruptcy") or "").strip()
        date_filed = (raw.get("Date Filed") or "").strip()
        if not (creditor and case_number and debtor and date_filed):
            warnings.append(f"line {line_number}: missing creditor/case/debtor/date — skipped")
            continue
        state = normalize_state(raw.get("State"))
        if state is None and (raw.get("State") or "").strip():
            warnings.append(
                f"line {line_number}: unusable State {raw.get('State')!r} — creditor kept without one"
            )
        rows.append(BkwireRow(
            date_filed=date_filed,
            creditor=creditor,
            debtor=debtor,
            case_number=case_number,
            city=(raw.get("City") or "").strip(),
            state=state,
            claim_amount=parse_loss(raw.get("Loss")),
            zone=(raw.get("BKwire Zone") or "").strip(),
            line_number=line_number,
        ))
    return rows, warnings


def group_by_case(rows: list[BkwireRow]) -> tuple[list[CaseGroup], int]:
    """Group rows by case, combining a creditor's multiple claims in that case.

    The export really does repeat a creditor within one case with different Loss
    values (9 of 100 rows in the 2026-08-04 sample) — separate claims, not
    duplicates. Summing them gives the creditor's true exposure, which is what
    the tiering and the report are about. Returns (groups, claims_combined).
    """
    groups: dict[str, CaseGroup] = {}
    merged: dict[tuple[str, str], dict] = {}
    combined = 0

    for row in rows:
        group = groups.get(row.case_number)
        if group is None:
            group = CaseGroup(case_number=row.case_number, debtor=row.debtor,
                              date_filed=row.date_filed)
            groups[row.case_number] = group

        key = (row.case_number, row.creditor.strip().lower())
        existing = merged.get(key)
        if existing is None:
            entry = {
                "creditor_name": row.creditor,
                "original_name": row.creditor,
                "address": format_address(row.city, row.state),
                "claim_amount": str(row.claim_amount) if row.claim_amount is not None else None,
                "confidence_score": str(_BKWIRE_CONFIDENCE),
                "source_line_numbers": [row.line_number],
            }
            merged[key] = entry
            group.creditors.append(entry)
            continue

        combined += 1
        existing["source_line_numbers"].append(row.line_number)
        if row.claim_amount is not None:
            prior = Decimal(existing["claim_amount"]) if existing["claim_amount"] else Decimal(0)
            existing["claim_amount"] = str(prior + row.claim_amount)
        # Keep the first non-empty address: the same creditor should not move
        # between rows, and the first is as good as any if it does.
        if not existing["address"]:
            existing["address"] = format_address(row.city, row.state)

    return list(groups.values()), combined


def filter_rows(rows: list[BkwireRow], states: set[str] | None) -> tuple[list[BkwireRow], int]:
    """Keep rows whose CREDITOR state is in ``states``; empty/None keeps everything.

    Note this filters on the creditor's location, which is NOT what the PACER
    path's court-district scope meant. Only 18% of the sample fell in the
    current target states, so this defaults to OFF until the client confirms the
    geography (see the module docstring / KD notes).
    """
    if not states:
        return rows, 0
    kept = [r for r in rows if r.state in states]
    return kept, len(rows) - len(kept)


# ---------------------------------------------------------------------------
# Supabase I/O
# ---------------------------------------------------------------------------

def _supabase_headers(key: str) -> dict[str, str]:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _upsert_bankruptcy(group: CaseGroup, settings: PipelineSettings) -> str:
    """Upsert the debtor's case row. See the module docstring on the sentinels."""
    with httpx.Client(timeout=settings.supabase_http_timeout_sec) as client:
        resp = client.post(
            f"{settings.supabase_url.rstrip('/')}/rest/v1/rpc/au_group_upsert_bankruptcy",
            headers={**_supabase_headers(settings.supabase_service_role_key),
                     "Prefer": "return=representation"},
            json={
                "p_case_number":    group.case_number,
                "p_debtor_name":    group.debtor,
                "p_filing_date":    group.date_filed,
                "p_court_district": _COURT_DISTRICT_SENTINEL,
                "p_chapter_type":   settings.bkwire_chapter_type,
                "p_state":          settings.bkwire_unknown_state,
            },
        )
        resp.raise_for_status()
    return str(resp.json())


def _merge_creditors(bankruptcy_id: str, creditors: list[dict],
                     settings: PipelineSettings) -> int:
    """Merge via the existing RPC — junk-name filtering and dedup stay in SQL."""
    with httpx.Client(timeout=settings.supabase_http_timeout_sec) as client:
        resp = client.post(
            f"{settings.supabase_url.rstrip('/')}/rest/v1/rpc/au_group_merge_creditor_matrix",
            headers=_supabase_headers(settings.supabase_service_role_key),
            json={"p_bankruptcy_id": bankruptcy_id, "p_creditors": creditors},
        )
        resp.raise_for_status()
    return int(resp.json() or 0)


def _enqueue_enrich(bankruptcy_id: str, settings: PipelineSettings) -> None:
    """Hand off to the existing zoom_info_enrich stage. No-ops if already queued."""
    with httpx.Client(timeout=settings.supabase_http_timeout_sec) as client:
        resp = client.post(
            f"{settings.supabase_url.rstrip('/')}/rest/v1/rpc/au_group_enqueue_job",
            headers=_supabase_headers(settings.supabase_service_role_key),
            json={"p_bankruptcy_id": bankruptcy_id, "p_job_type": "zoom_info_enrich"},
        )
        resp.raise_for_status()


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------

def ingest_text(text: str, *, dry_run: bool = False,
                settings: PipelineSettings | None = None) -> BkwireIngestResult:
    """Parse a BKwire export and load it into the existing pipeline tables."""
    s = settings or get_pipeline_settings()
    result = BkwireIngestResult()

    rows, warnings = parse_csv(text)
    result.warnings.extend(warnings)
    result.rows_read = len(rows) + sum(1 for w in warnings if "skipped" in w)
    result.rows_skipped = sum(1 for w in warnings if "skipped" in w)

    states = {st.strip().upper() for st in (s.bkwire_state_filter or "").split(",") if st.strip()}
    rows, filtered_out = filter_rows(rows, states)
    if filtered_out:
        logger.info("BKwire: %d row(s) outside the creditor-state filter %s", filtered_out, sorted(states))

    groups, combined = group_by_case(rows)
    result.cases = len(groups)
    result.claims_combined = combined

    logger.info(
        "BKwire: %d row(s) → %d case(s), %d combined claim row(s). chapter_type=%r "
        "(the feed carries no chapter)",
        len(rows), len(groups), combined, s.bkwire_chapter_type,
    )

    if dry_run:
        for g in groups:
            logger.info("[DRY-RUN] %s | %s | filed %s | %d creditor(s)",
                        g.case_number, g.debtor, g.date_filed, len(g.creditors))
        return result

    for group in groups:
        try:
            bankruptcy_id = _upsert_bankruptcy(group, s)
            result.creditors_merged += _merge_creditors(bankruptcy_id, group.creditors, s)
            _enqueue_enrich(bankruptcy_id, s)
        except Exception as exc:  # noqa: BLE001 — one bad case must not drop the file
            logger.error("BKwire: case %s failed: %s", group.case_number, exc)
            result.errors.append(f"{group.case_number}: {exc}")
            continue

    return result


def ingest_file(path: str, *, dry_run: bool = False,
                settings: PipelineSettings | None = None) -> BkwireIngestResult:
    with open(path, encoding="utf-8-sig") as fh:      # exports carry a BOM
        return ingest_text(fh.read(), dry_run=dry_run, settings=settings)


def main() -> None:
    import argparse
    import sys

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    parser = argparse.ArgumentParser(description="Ingest a BKwire creditor export")
    parser.add_argument("path", help="path to the BKwire CSV export")
    parser.add_argument("--dry-run", action="store_true",
                        help="parse and report without writing to Supabase")
    args = parser.parse_args()

    result = ingest_file(args.path, dry_run=args.dry_run)
    logger.info(
        "BKwire ingest complete: rows=%d skipped=%d cases=%d creditors_merged=%d "
        "claims_combined=%d errors=%d",
        result.rows_read, result.rows_skipped, result.cases, result.creditors_merged,
        result.claims_combined, len(result.errors),
    )
    for warning in result.warnings:
        logger.warning("  - %s", warning)
    for err in result.errors:
        logger.error("  - %s", err)
    sys.exit(1 if result.errors else 0)


if __name__ == "__main__":
    main()
