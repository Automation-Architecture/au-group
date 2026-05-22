import re

from app.extractors.structured_pdf import StructuredPdfResult
from app.models.schemas import CountRange, Form201Data, UsdRange

USD_RANGE_PATTERNS = [
    (
        re.compile(
            r"\$\s*([\d,]+(?:\.\d+)?)\s*(?:to|-|–)\s*\$?\s*([\d,]+(?:\.\d+)?)",
            re.I,
        ),
        1.0,
        1_000_000.0,
    ),
    (re.compile(r"\$\s*([\d,]+(?:\.\d+)?)\s*or\s+more", re.I), 1.0, None),
    (re.compile(r"less\s+than\s+\$?\s*([\d,]+(?:\.\d+)?)", re.I), None, 1.0),
]

CREDITOR_COUNT_PATTERNS = [
    re.compile(r"(\d+)\s*(?:to|-|–)\s*(\d+)\s*creditors?", re.I),
    re.compile(r"(\d+)\s*or\s+more\s*creditors?", re.I),
    re.compile(r"less\s+than\s+(\d+)\s*creditors?", re.I),
]


def _parse_money(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = value.replace(",", "").replace("$", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _find_usd_range(text: str, label: str) -> UsdRange | None:
    section = text
    label_match = re.search(re.escape(label), text, re.I)
    if label_match:
        section = text[label_match.start() : label_match.start() + 800]
    for pattern, default_min, default_max in USD_RANGE_PATTERNS:
        match = pattern.search(section)
        if not match:
            continue
        groups = match.groups()
        if len(groups) == 2:
            return UsdRange(
                min_usd=_parse_money(groups[0]),
                max_usd=_parse_money(groups[1]),
            )
        if default_min is None:
            return UsdRange(min_usd=None, max_usd=_parse_money(groups[0]))
        return UsdRange(min_usd=_parse_money(groups[0]), max_usd=default_max)
    return None


def _find_creditor_count(text: str) -> CountRange | None:
    section = text
    anchor = re.search(r"creditors?", text, re.I)
    if anchor:
        start = max(0, anchor.start() - 200)
        section = text[start : anchor.start() + 400]
    for pattern in CREDITOR_COUNT_PATTERNS:
        match = pattern.search(section)
        if not match:
            continue
        groups = match.groups()
        if len(groups) == 2:
            return CountRange(min=int(groups[0]), max=int(groups[1]))
        if "or more" in match.group(0).lower():
            return CountRange(min=int(groups[0]), max=None)
        return CountRange(min=None, max=int(groups[0]))
    return None


def _find_field(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.M)
        if match and match.lastindex:
            value = match.group(1).strip()
            if value:
                return value
    return None


def extract_form201(text: str, structured: StructuredPdfResult | None = None) -> Form201Data:
    debtor_name = _find_field(
        text,
        [
            r"Debtor\s+1[:\s]+(.+?)(?:\n|$)",
            r"Name of debtor[:\s]+(.+?)(?:\n|$)",
            r"Debtor(?:'s)?\s+name[:\s]+(.+?)(?:\n|$)",
        ],
    )
    city = _find_field(text, [r"City[:\s]+([A-Za-z .'-]+)"])
    state = _find_field(text, [r"State[:\s]+([A-Z]{2})\b", r"\b([A-Z]{2})\s+\d{5}"])
    court_district = _find_field(
        text,
        [
            r"(United States Bankruptcy Court.+?District of [^\n]+)",
            r"(District of [^\n]+)",
        ],
    )
    industry_code = _find_field(
        text,
        [
            r"NAICS[:\s]+(\d{6})",
            r"Nature of business[:\s]+.*?(\d{6})",
        ],
    )

    assets = _find_usd_range(text, "estimated assets")
    liabilities = _find_usd_range(text, "estimated liabilities")
    creditor_count = _find_creditor_count(text)

    if structured and structured.tables:
        table_text = "\n".join(
            " ".join(cell or "" for cell in row) for table in structured.tables for row in table
        )
        assets = assets or _find_usd_range(table_text, "assets")
        liabilities = liabilities or _find_usd_range(table_text, "liabilities")

    return Form201Data(
        debtor_name=debtor_name,
        city=city,
        state=state,
        court_district=court_district,
        industry_code=industry_code,
        estimated_assets=assets,
        estimated_liabilities=liabilities,
        estimated_creditor_count=creditor_count,
    )
