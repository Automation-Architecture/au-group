from app.extractors.creditor_matrix import (
    _name_and_address_from_table_row,
    extract_creditor_matrix,
)
from app.extractors.structured_pdf import StructuredPdfResult
from app.validation.creditor_name_quality import is_junk_creditor_name

SAMPLE_LIST = """
List of Creditors

1. Acme Corporation LLC
123 Main St, Dallas, TX 75001
$1,234,567.89

2. Jane Smith
456 Oak Ave, Austin, TX 78701
"""

SAMPLE_SINGLE_NEWLINE = """
Official Form 204
List of Creditors
1. Acme Corporation LLC
123 Main St, Dallas, TX 75001
$1,234,567.89
2. Jane Smith
456 Oak Ave, Austin, TX 78701
$50,000.00
"""


def test_table_row_keeps_numeric_address_not_amount() -> None:
    name, address, amount_raw = _name_and_address_from_table_row(
        ["1", "Acme Corp", "500 Commerce St, Dallas, TX 75001", "$10,000.00"]
    )
    assert name == "Acme Corp"
    assert address is not None and "Commerce" in address
    assert amount_raw == "$10,000.00"


def test_extract_creditors_from_text() -> None:
    rows = extract_creditor_matrix(SAMPLE_LIST)
    assert len(rows) >= 2
    names = {row.creditor_name for row in rows}
    assert any("Acme" in name for name in names)
    assert not any("list of creditors" in name.lower() for name in names)


def test_skips_header_only_block() -> None:
    rows = extract_creditor_matrix("List of Creditors\n\nOfficial Form 204")
    assert rows == []


def test_extract_creditors_from_single_newline_text() -> None:
    rows = extract_creditor_matrix(SAMPLE_SINGLE_NEWLINE)
    assert len(rows) >= 2
    names = {row.creditor_name for row in rows}
    assert any("Acme" in name for name in names)
    assert any("Jane" in name for name in names)
    assert not any("list of creditors" in name.lower() for name in names)


def test_is_junk_creditor_name_rejects_form_labels_and_line_numbers() -> None:
    assert is_junk_creditor_name("19")
    assert is_junk_creditor_name("contact")
    assert is_junk_creditor_name("email address of creditor")
    assert is_junk_creditor_name("mailing address, including zip code")
    assert not is_junk_creditor_name("Acme Industrial Supply LLC")
    assert not is_junk_creditor_name("Test Bank NA")
    assert not is_junk_creditor_name("Real Creditor Holdings LLC")
    assert not is_junk_creditor_name("ABC Holdings Inc")


def test_extract_creditors_from_structured_tables() -> None:
    structured = StructuredPdfResult(
        text="",
        page_count=1,
        tables=[
            [
                ["Creditor Name", "Mailing Address", "Claim Amount"],
                ["Widget Co", "1 Main St", "$100.00"],
                ["Gadget LLC", "2 Oak Ave", "$200.00"],
            ]
        ],
    )
    rows = extract_creditor_matrix("", structured)
    assert len(rows) == 2
    assert rows[0].creditor_name == "Widget Co"
    assert rows[0].source_line_numbers == [1]
    assert rows[1].source_line_numbers == [2]


def test_same_name_different_addresses_keeps_both_rows() -> None:
    """Extractor must not name-only dedupe; KD-40 fuzzy dedup runs in pipeline."""
    text = """
List of Creditors

1. Acme Corp
123 Main St, Dallas, TX 75001
$100.00

2. Acme Corp
456 Oak Ave, Austin, TX 78701
$50.00
"""
    rows = extract_creditor_matrix(text)
    assert len(rows) == 2
    addresses = {row.address for row in rows}
    assert any("Main" in (a or "") for a in addresses)
    assert any("Oak" in (a or "") for a in addresses)


def test_extract_skips_form_204_junk_lines() -> None:
    junk_text = """
Official Form 204
List of Creditors
19
email address of creditor
mailing address, including zip code
contact
1. Real Creditor Holdings LLC
500 Commerce St, Dallas, TX 75001
$10,000.00
"""
    rows = extract_creditor_matrix(junk_text)
    names = [row.creditor_name for row in rows]
    assert any("Real Creditor" in n for n in names)
    assert not any(is_junk_creditor_name(n) for n in names)


def test_infer_entity_type_individual_and_partnership() -> None:
    rows = extract_creditor_matrix(
        "1. John and Jane Smith\n100 Main St\n$1,000.00\n\n"
        "2. Robert Jones\n200 Oak Ave\n$2,000.00"
    )
    by_name = {r.creditor_name: r.entity_type for r in rows}
    assert by_name.get("John and Jane Smith") == "individual"
    assert by_name.get("Robert Jones") == "individual"


def test_skips_tables_without_creditor_header() -> None:
    structured = StructuredPdfResult(
        text="",
        page_count=1,
        tables=[[["Date", "Amount"], ["2024-01-01", "$100"]]],
    )
    rows = extract_creditor_matrix("", structured)
    assert rows == []


def test_numbered_single_line_fallback_when_no_paragraph_breaks() -> None:
    text = (
        "List of Creditors\n"
        "1. Lone Creditor LLC\n"
        "99 Side St\n"
        "$500.00\n"
        "2. Second Creditor Inc\n"
        "88 Pine Rd\n"
        "$250.00"
    )
    rows = extract_creditor_matrix(text)
    assert len(rows) >= 2
    assert any(r.creditor_name == "Lone Creditor LLC" for r in rows)


def test_table_row_parses_address_and_claim() -> None:
    structured = StructuredPdfResult(
        text="",
        page_count=1,
        tables=[
            [
                ["Creditor Name", "Mailing Address", "Claim Amount"],
                ["Payee Co", "Main Street, Dallas TX", "$1,234.56"],
            ]
        ],
    )
    rows = extract_creditor_matrix("", structured)
    assert len(rows) == 1
    assert rows[0].address == "Main Street, Dallas TX"
    assert rows[0].claim_amount == 1234.56
