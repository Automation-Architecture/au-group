"""Company name normalization for ZoomInfo lookup keys (KD-20 / KD-24).

Runtime source of truth: Postgres ``au_group_normalize_company_name`` and
``au_group_company_name_rules``. This module mirrors the default suffix-strip
+ punctuation collapse for unit tests and offline tooling only.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_SUFFIX_RE = re.compile(
    r"\s+(incorporated|inc|corp|corporation|llc|l\.l\.c\.|ltd|limited|co|company)\.?\s*$",
    re.IGNORECASE,
)
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class CompanyNameRule:
    rule_type: str
    pattern: str
    replacement: str = ""


DEFAULT_RULES: tuple[CompanyNameRule, ...] = (
    CompanyNameRule(
        rule_type="suffix_strip",
        pattern=(
            r"\s+(incorporated|inc|corp|corporation|llc|l\.l\.c\.|ltd|limited|co|company)\.?\s*$"
        ),
    ),
)


def normalize_company_name(
    name: str,
    rules: tuple[CompanyNameRule, ...] | None = None,
) -> str:
    """Apply KD-24-style rules (default: suffix strip + uppercase punctuation collapse)."""
    cleaned = (name or "").strip()
    if not cleaned:
        return ""

    for rule in rules if rules is not None else DEFAULT_RULES:
        if rule.rule_type == "suffix_strip":
            cleaned = re.sub(rule.pattern, rule.replacement, cleaned, flags=re.IGNORECASE)
        elif rule.rule_type == "alias":
            if cleaned.upper() == rule.pattern.upper():
                cleaned = rule.replacement or cleaned
        elif rule.rule_type == "token_replace":
            cleaned = re.sub(rule.pattern, rule.replacement, cleaned, flags=re.IGNORECASE)

    cleaned = _PUNCT_RE.sub(" ", cleaned.upper())
    return _WS_RE.sub(" ", cleaned).strip()


def build_company_lookup_cache_key(name: str, address: str | None = None) -> str:
    """MD5 key aligned with au_group_company_lookup_cache_key (name|address)."""
    norm_name = normalize_company_name(name)
    norm_addr = _WS_RE.sub(" ", (address or "").upper().strip())
    payload = f"{norm_name}|{norm_addr}"
    return hashlib.md5(payload.encode("utf-8")).hexdigest()
