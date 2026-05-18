"""S3 key prefix and path validation."""

from __future__ import annotations

import re
from typing import Literal

READ_PREFIX = "raw-documents/"
WRITE_PREFIXES = ("ocr-outputs/", "parsed-outputs/")

# raw-documents/{case_number}/{document_id}.pdf
_READ_KEY_PATTERN = re.compile(
    r"^raw-documents/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+\.pdf$"
)
_WRITE_KEY_PATTERN = re.compile(
    r"^(?:ocr-outputs|parsed-outputs)/[A-Za-z0-9._-]+/[A-Za-z0-9._-]+\.(?:txt|json)$"
)


def _reject_unsafe_key(s3_key: str) -> None:
    if not s3_key or not s3_key.strip():
        raise ValueError("s3_key must not be empty")
    if s3_key != s3_key.strip():
        raise ValueError("s3_key must not have leading or trailing whitespace")
    if "\x00" in s3_key:
        raise ValueError("s3_key contains invalid characters")
    if s3_key.startswith("/") or "\\" in s3_key or ".." in s3_key:
        raise ValueError("s3_key path is not allowed")


def validate_s3_key(s3_key: str, *, operation: Literal["read", "write"]) -> str:
    _reject_unsafe_key(s3_key)
    if operation == "read":
        if not s3_key.startswith(READ_PREFIX):
            raise ValueError("s3_key must be under raw-documents/")
        if not _READ_KEY_PATTERN.fullmatch(s3_key):
            raise ValueError("s3_key format is invalid")
        return s3_key
    if not any(s3_key.startswith(prefix) for prefix in WRITE_PREFIXES):
        raise ValueError("s3_key must be under ocr-outputs/ or parsed-outputs/")
    if not _WRITE_KEY_PATTERN.fullmatch(s3_key):
        raise ValueError("s3_key format is invalid")
    return s3_key
