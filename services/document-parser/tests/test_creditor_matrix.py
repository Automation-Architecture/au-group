from app.extractors.creditor_matrix import extract_creditor_matrix
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
