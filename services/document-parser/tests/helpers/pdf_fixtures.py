"""Generate minimal PDFs with embedded text for integration tests."""

from pathlib import Path

import fitz

FORM201_TEXT = """
Official Form 201
Voluntary Petition
Debtor 1: Michael J Lombardo
City: New York
State: NY
United States Bankruptcy Court for the Southern District of New York
NAICS: 531120
estimated assets $1,000,000 to $10,000,000
estimated liabilities $10,000,000 to $50,000,000
200 to 999 creditors
"""

CREDITOR_MATRIX_TEXT = """
Official Form 204
List of Creditors


1. Acme Corporation LLC
123 Main St, Dallas, TX 75001
$1,234,567.89


2. Jane Smith
456 Oak Ave, Austin, TX 78701
$50,000.00
"""

# KD-40: intentional fuzzy duplicates (ABC Corp / ABC Corporation, same address)
CREDITOR_MATRIX_DEDUP_TEXT = """
Official Form 204
List of Creditors


1. ABC Corp
123 Main St, Dallas, TX 75001
$100.00


2. ABC Corporation
123 Main St, Dallas, TX 75001
$50.00


3. Jane Smith
456 Oak Ave, Austin, TX 78701
$25.00
"""

# KD-40: intentional fuzzy duplicates on Schedule E/F path
SCHEDULE_EF_DEDUP_TEXT = """
Official Form 206E/F
Schedule E/F — Creditors Holding Unsecured Nonpriority Claims


1. ABC Corp
123 Main St, Dallas, TX 75001
$100.00


2. ABC Corporation
123 Main St, Dallas, TX 75001
$50.00
"""

SCHEDULE_EF_TEXT = """
Official Form 206E/F
Schedule E/F — Creditors Holding Unsecured Nonpriority Claims


1. Widget Industries LLC
100 Pine St, Boston, MA 02101
$75,000.00


2. Robert Jones
200 Elm Ave, Cambridge, MA 02139
$12,500.00
"""

# KD-40: same canonical name, different addresses — must NOT merge
CREDITOR_MATRIX_SAME_NAME_DIFF_ADDR_TEXT = """
Official Form 204
List of Creditors


1. Acme Corp
123 Main St, Dallas, TX 75001
$100.00


2. Acme Corp
456 Oak Ave, Austin, TX 78701
$50.00
"""


def write_text_pdf(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    y = 72
    line_height = 14
    for line in body.strip().splitlines():
        if not line.strip():
            y += line_height
            continue
        page.insert_text((72, y), line, fontsize=10)
        y += line_height
        if y > 720:
            page = doc.new_page(width=612, height=792)
            y = 72
    doc.save(path)
    doc.close()


def build_integration_pdfs(directory: Path) -> tuple[Path, Path]:
    form201_path = directory / "form201.pdf"
    matrix_path = directory / "creditor_matrix.pdf"
    write_text_pdf(form201_path, FORM201_TEXT)
    write_text_pdf(matrix_path, CREDITOR_MATRIX_TEXT)
    return form201_path, matrix_path
