"""Shared creditor-name junk detection (parser + validation).

DB RPCs use public.au_group_is_junk_creditor_name() with thresholds from
au_group_runtime_config (creditor_name_min_length, creditor_line_number_max_digits).
Parser defaults must match via Settings env vars.
"""

import re
from functools import lru_cache

from app.core.config import get_settings

HEADER_PATTERN = re.compile(
    r"^(list of creditors|creditor matrix|creditors holding|official form 204|"
    r"20 largest unsecured|name of creditor|creditor\s*name)\b",
    re.I,
)

JUNK_NAME_SUBSTRINGS = re.compile(
    r"(mailing address|email address|name of creditor|including zip|zip code|"
    r"nature of claim|account number|official form|form\s*204|"
    r"list of creditors|creditor matrix|claim amount)",
    re.I,
)

JUNK_EXACT_NAMES = frozenset(
    {
        "contact",
        "contacts",
        "name",
        "address",
        "amount",
        "claim",
        "creditor",
        "creditors",
        "total",
    }
)


@lru_cache(maxsize=4)
def _pure_digit_pattern(max_digits: int) -> re.Pattern[str]:
    return re.compile(rf"^\d{{1,{max_digits}}}$")


def is_junk_creditor_name(name: str) -> bool:
    """Reject Form 204 field labels, line numbers, and other non-creditor tokens."""
    settings = get_settings()
    min_length = settings.creditor_name_min_length
    max_line_digits = settings.creditor_line_number_max_digits

    cleaned = name.strip()
    if len(cleaned) < min_length:
        return True
    lower = cleaned.lower()
    if lower in JUNK_EXACT_NAMES:
        return True
    if _pure_digit_pattern(max_line_digits).match(cleaned):
        return True
    if HEADER_PATTERN.search(cleaned):
        return True
    if JUNK_NAME_SUBSTRINGS.search(cleaned):
        return True
    return False
