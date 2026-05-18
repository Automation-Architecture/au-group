import re

from app.extractors.structured_pdf import StructuredPdfResult
from app.models.schemas import CreditorRow

ENTITY_SUFFIXES = re.compile(
    r"\b(LLC|L\.L\.C\.|Inc\.?|Corp\.?|Corporation|Ltd\.?|LP|LLP|Co\.)\b",
    re.I,
)

HEADER_PATTERN = re.compile(
    r"^(list of creditors|creditor matrix|creditors holding|official form 204|"
    r"20 largest unsecured|name of creditor|creditor\s*name)\b",
    re.I,
)

NUMBERED_LINE_START = re.compile(r"^\d+\.\s+")


def _infer_entity_type(name: str) -> str:
    if ENTITY_SUFFIXES.search(name):
        return "company"
    if re.search(r"\b(and|&)\b", name, re.I) and len(name.split()) >= 3:
        return "individual"
    parts = name.split()
    if len(parts) >= 2 and parts[0][0].isupper() and parts[1][0].isupper():
        return "individual"
    return "company"


def _parse_claim_amount(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = re.sub(r"[^\d.]", "", value.replace(",", ""))
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _rows_from_tables(structured: StructuredPdfResult) -> list[CreditorRow]:
    creditors: list[CreditorRow] = []
    for table in structured.tables:
        if not table or len(table) < 2:
            continue
        header = " ".join(cell or "" for cell in table[0]).lower()
        if "creditor" not in header and "name" not in header:
            continue
        for row in table[1:]:
            if not row or not any(row):
                continue
            name = (row[0] or "").strip()
            if not name or len(name) < 2:
                continue
            address = (row[1] or "").strip() if len(row) > 1 else None
            amount_raw = row[2] if len(row) > 2 else None
            creditors.append(
                CreditorRow(
                    creditor_name=name,
                    address=address or None,
                    claim_amount=_parse_claim_amount(amount_raw or ""),
                    entity_type=_infer_entity_type(name),
                )
            )
    return creditors


def _rows_from_text(text: str) -> list[CreditorRow]:
    creditors: list[CreditorRow] = []
    blocks = re.split(r"\n{2,}", text)
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 1:
            continue
        first = lines[0]
        if len(first) < 3 or HEADER_PATTERN.search(first):
            continue
        numbered = re.match(r"^\d+\.?\s+", first)
        if not numbered and len(lines) < 2 and "$" not in block:
            continue
        if numbered:
            first = re.sub(r"^\d+\.?\s+", "", first)
        address = ", ".join(lines[1:3]) if len(lines) > 1 else None
        amount_match = re.search(r"\$\s*[\d,]+(?:\.\d+)?", block)
        creditors.append(
            CreditorRow(
                creditor_name=first,
                address=address,
                claim_amount=_parse_claim_amount(amount_match.group(0) if amount_match else None),
                entity_type=_infer_entity_type(first),
            )
        )
    return creditors


def _block_to_creditor_row(lines: list[str]) -> CreditorRow | None:
    if not lines:
        return None
    first = lines[0]
    if len(first) < 3 or HEADER_PATTERN.search(first):
        return None
    name = re.sub(r"^\d+\.?\s+", "", first)
    if not name or len(name) < 2:
        return None
    address = ", ".join(lines[1:3]) if len(lines) > 1 else None
    block_text = "\n".join(lines)
    amount_match = re.search(r"\$\s*[\d,]+(?:\.\d+)?", block_text)
    return CreditorRow(
        creditor_name=name,
        address=address,
        claim_amount=_parse_claim_amount(amount_match.group(0) if amount_match else None),
        entity_type=_infer_entity_type(name),
    )


def _rows_from_numbered_lines(text: str) -> list[CreditorRow]:
    """Fallback when pdfplumber flattens paragraphs to single newlines."""
    creditors: list[CreditorRow] = []
    current_lines: list[str] = []

    def flush() -> None:
        row = _block_to_creditor_row(current_lines)
        if row:
            creditors.append(row)

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if NUMBERED_LINE_START.match(line):
            if current_lines:
                flush()
            current_lines = [line]
        elif current_lines:
            current_lines.append(line)
    if current_lines:
        flush()
    return creditors


def extract_creditor_matrix(
    text: str, structured: StructuredPdfResult | None = None
) -> list[CreditorRow]:
    creditors: list[CreditorRow] = []
    if structured:
        creditors.extend(_rows_from_tables(structured))
    if not creditors:
        creditors.extend(_rows_from_text(text))
    if not creditors:
        creditors.extend(_rows_from_numbered_lines(text))
    seen: set[str] = set()
    unique: list[CreditorRow] = []
    for row in creditors:
        key = row.creditor_name.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique
