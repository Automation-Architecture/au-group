"""S3 key validation tests."""

import pytest
from app.core.s3_validation import validate_s3_key


def test_accepts_valid_read_key() -> None:
    key = "raw-documents/24-10001/a1b2c3d4-uuid.pdf"
    assert validate_s3_key(key, operation="read") == key


def test_rejects_path_traversal() -> None:
    with pytest.raises(ValueError, match="not allowed"):
        validate_s3_key("raw-documents/../secrets.pdf", operation="read")


def test_rejects_wrong_prefix() -> None:
    with pytest.raises(ValueError, match="raw-documents"):
        validate_s3_key("parsed-outputs/24-10001/x.pdf", operation="read")


def test_rejects_non_pdf_read() -> None:
    with pytest.raises(ValueError, match="format"):
        validate_s3_key("raw-documents/24-10001/doc.txt", operation="read")


def test_accepts_valid_write_keys() -> None:
    txt = "ocr-outputs/24-10001/doc-id.txt"
    json_key = "parsed-outputs/24-10001/doc-id.json"
    assert validate_s3_key(txt, operation="write") == txt
    assert validate_s3_key(json_key, operation="write") == json_key


def test_rejects_invalid_write_prefix() -> None:
    with pytest.raises(ValueError, match="ocr-outputs"):
        validate_s3_key("raw-documents/24-10001/x.pdf", operation="write")
