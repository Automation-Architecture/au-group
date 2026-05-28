"""Company name normalization for ZoomInfo lookup keys (KD-20 / KD-24)."""

from __future__ import annotations

import hashlib
import re

_SUFFIX_RE = re.compile(
    r"\s+(incorporated|inc|corp|corporation|llc|l\.l\.c\.|ltd|limited|co|company)\.?\s*$",
    re.IGNORECASE,
)
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def normalize_company_name(name: str) -> str:
    """Strip legal suffixes and punctuation; uppercase for stable cache keys."""
    cleaned = (name or "").strip()
    cleaned = _SUFFIX_RE.sub("", cleaned)
    cleaned = _PUNCT_RE.sub(" ", cleaned.upper())
    return _WS_RE.sub(" ", cleaned).strip()


def build_company_lookup_cache_key(name: str, address: str | None = None) -> str:
    """MD5 key aligned with au_group_company_lookup_cache_key (name|address)."""
    norm_name = normalize_company_name(name)
    norm_addr = _WS_RE.sub(" ", (address or "").upper().strip())
    payload = f"{norm_name}|{norm_addr}"
    return hashlib.md5(payload.encode("utf-8")).hexdigest()
