from pathlib import Path

import pytest
from app.extractors.schedules import (
    _is_schedule_table,
    _rows_from_schedule_tables,
    parse_schedule_ab,
    parse_schedule_d,
    parse_schedule_ef,
    parse_sofa,
)
from app.extractors.structured_pdf import StructuredPdfResult
from tests.helpers.pdf_fixtures import SCHEDULE_EF_TEXT, write_text_pdf


def test_parse_schedule_ef_numbered_list() -> None:
    rows = parse_schedule_ef(SCHEDULE_EF_TEXT)
    assert len(rows) == 2
    names = {r.creditor_name for r in rows}
    assert "Widget Industries LLC" in names
    assert "Robert Jones" in names
    widget = next(r for r in rows if "Widget" in r.creditor_name)
    assert widget.claim_amount == pytest.approx(75_000.0)
    assert widget.source_line_numbers == [1]


def test_parse_schedule_ef_empty_text() -> None:
    assert parse_schedule_ef("") == []


def test_parse_schedule_ab_still_deferred() -> None:
    with pytest.raises(NotImplementedError):
        parse_schedule_ab("sample")


def test_parse_schedule_ef_from_structured_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "schedule_ef.pdf"
    write_text_pdf(pdf_path, SCHEDULE_EF_TEXT)
    from app.extractors.structured_pdf import extract_structured_pdf

    structured = extract_structured_pdf(pdf_path)
    rows = parse_schedule_ef(structured.text, structured)
    assert len(rows) >= 2


def test_is_schedule_table_rejects_invalid_tables() -> None:
    assert _is_schedule_table([]) is False
    assert _is_schedule_table([["only one row"]]) is False


def test_is_schedule_table_matches_creditor_and_claim_header() -> None:
    table = [
        ["Creditor Name", "Mailing Address", "Claim Amount"],
        ["Table Co LLC", "9 Bay Rd", "$1,000.00"],
    ]
    assert _is_schedule_table(table) is True


def test_rows_from_schedule_tables_extracts_body_rows() -> None:
    structured = StructuredPdfResult(
        text="",
        page_count=1,
        tables=[
            [
                ["Schedule E/F — Unsecured Claims"],
                ["Creditor", "Address", "Amount"],
                ["Table Co LLC", "9 Bay Rd", "$1,000.00"],
            ]
        ],
    )
    rows = _rows_from_schedule_tables(structured)
    assert len(rows) == 1
    assert rows[0].creditor_name == "Table Co LLC"
    assert rows[0].claim_amount == pytest.approx(1000.0)
    assert rows[0].source_line_numbers == [2]


def test_parse_schedule_ef_uses_structured_tables_before_text_fallback() -> None:
    table = [
        ["Creditor Name", "Address", "Claim Amount"],
        ["Structured Only Inc", "1 A St", "$500"],
    ]
    structured = StructuredPdfResult(text="", page_count=1, tables=[table])
    rows = parse_schedule_ef("no numbered creditors in plain text", structured)
    assert len(rows) == 1
    assert rows[0].creditor_name == "Structured Only Inc"


def test_parse_schedule_d_and_sofa_still_deferred() -> None:
    with pytest.raises(NotImplementedError):
        parse_schedule_d("sample")
    with pytest.raises(NotImplementedError):
        parse_sofa("sample")
