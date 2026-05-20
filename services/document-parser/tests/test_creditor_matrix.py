from app.extractors.creditor_matrix import extract_creditor_matrix


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
