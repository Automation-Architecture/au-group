from uuid import uuid4

import pytest
from app.core.exceptions import DocumentProcessingError
from app.pipeline.job_status import processing_placeholder_raw
from app.pipeline.router import DocumentPipeline


def test_force_while_processing_raises() -> None:
    pipeline = DocumentPipeline()
    existing = {
        "id": str(uuid4()),
        "filing_type": "UNKNOWN",
        "parse_mode": "structured",
        "ocr_used": False,
        "page_count": 0,
        "raw_extraction": processing_placeholder_raw(),
    }

    def fake_find(_hash: str, _version: str) -> dict:
        return existing

    pipeline._db.find_document_by_hash = fake_find  # type: ignore[method-assign]

    with pytest.raises(DocumentProcessingError, match="still processing"):
        pipeline._lookup_cached_document("deadbeef", force=True)


def test_resolve_document_id_reuses_existing_hash_row() -> None:
    pipeline = DocumentPipeline()
    existing_id = uuid4()
    content_hash = "deadbeef"

    def fake_find(_hash: str, _version: str) -> dict:
        return {"id": str(existing_id)}

    pipeline._db.find_document_by_hash = fake_find  # type: ignore[method-assign]

    resolved = pipeline._resolve_document_id(document_id=None, content_hash=content_hash)
    assert resolved == existing_id


def test_resolve_document_id_prefers_explicit_document_id() -> None:
    pipeline = DocumentPipeline()
    explicit_id = uuid4()

    resolved = pipeline._resolve_document_id(
        document_id=explicit_id, content_hash="deadbeef"
    )
    assert resolved == explicit_id


def test_invalid_review_status_raises() -> None:
    from app.persistence.review_status import validate_review_queue_status

    with pytest.raises(ValueError, match="Invalid status"):
        validate_review_queue_status("pending' OR '1'='1")
