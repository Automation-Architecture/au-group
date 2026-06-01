"""
Schedule E/F (Form 206E/F) creditor extraction.

Reuses table/text fallbacks from creditor_matrix; schedule tables are detected by header keywords.
"""

from __future__ import annotations

from app.extractors.creditor_matrix import (
    _infer_entity_type,
    _name_and_address_from_table_row,
    _parse_claim_amount,
    _rows_from_numbered_lines,
    _rows_from_text,
)
from app.extractors.structured_pdf import StructuredPdfResult
from app.models.schemas import CreditorRow
from app.validation.creditor_name_quality import is_junk_creditor_name

SCHEDULE_TABLE_HEADER_KEYWORDS = (
    "schedule e",
    "schedule f",
    "206e",
    "206f",
    "unsecured",
    "nature of claim",
    "creditors holding",
)


def _is_schedule_table(table: list[list]) -> bool:
    if not table or len(table) < 2:
        return False
    header = " ".join(cell or "" for cell in table[0]).lower()
    if any(keyword in header for keyword in SCHEDULE_TABLE_HEADER_KEYWORDS):
        return True
    return "creditor" in header and ("claim" in header or "amount" in header)


def _rows_from_schedule_tables(structured: StructuredPdfResult) -> list[CreditorRow]:
    creditors: list[CreditorRow] = []
    for table in structured.tables:
        if not _is_schedule_table(table):
            continue
        for row_index, row in enumerate(table[1:], start=1):
            if not row or not any(row):
                continue
            name, address, amount_raw = _name_and_address_from_table_row(row)
            if not name or is_junk_creditor_name(name):
                continue
            creditors.append(
                CreditorRow(
                    creditor_name=name,
                    address=address,
                    claim_amount=_parse_claim_amount(amount_raw or ""),
                    entity_type=_infer_entity_type(name),
                    source_line_numbers=[row_index],
                )
            )
    return creditors


def parse_schedule_ab(_text: str) -> list[CreditorRow]:
    raise NotImplementedError("SCHEDULE_A_B parser deferred to Phase 2")


def parse_schedule_d(_text: str) -> list[CreditorRow]:
    raise NotImplementedError("SCHEDULE_D parser deferred to Phase 2")


def parse_schedule_ef(
    text: str, structured: StructuredPdfResult | None = None
) -> list[CreditorRow]:
    """Extract unsecured creditors from Schedule E/F (Form 206E/F) filings."""
    creditors: list[CreditorRow] = []
    if structured:
        creditors.extend(_rows_from_schedule_tables(structured))
    if not creditors:
        creditors.extend(_rows_from_text(text))
    if not creditors:
        creditors.extend(_rows_from_numbered_lines(text))
    return [row for row in creditors if not is_junk_creditor_name(row.creditor_name)]


def parse_sofa(_text: str) -> dict:
    raise NotImplementedError("SOFA parser deferred to Phase 2")
