from uuid import UUID, uuid4

import pytest
from app.core.exceptions import DocumentProcessingError
from app.models.schemas import (
    CreditorRow,
    FilingType,
    ParseDocumentResponse,
    ParseMode,
    ValidationResult,
)
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

    resolved = pipeline._resolve_document_id(document_id=explicit_id, content_hash="deadbeef")
    assert resolved == explicit_id


def test_invalid_review_status_raises() -> None:
    from app.persistence.review_status import validate_review_queue_status

    with pytest.raises(ValueError, match="Invalid status"):
        validate_review_queue_status("pending' OR '1'='1")


def test_backfill_creditor_merge_calls_merge() -> None:
    pipeline = DocumentPipeline()
    pipeline._db._enabled = True
    bankruptcy_id = uuid4()
    creditors = [CreditorRow(creditor_name="Acme Corp")]
    response = ParseDocumentResponse(
        status="completed",
        filing_type=FilingType.CREDITOR_MATRIX,
        parse_mode=ParseMode.STRUCTURED,
        ocr_used=False,
        page_count=1,
        confidence=0.92,
        manual_review_required=False,
        creditors=creditors,
        validation=ValidationResult(
            confidence_score=0.92,
            manual_review_required=False,
        ),
    )
    merge_calls: list[tuple[UUID, int]] = []

    def fake_merge(
        bid: UUID,
        rows: list[CreditorRow],
        *,
        confidence_score: float | None = None,
    ) -> int:
        merge_calls.append((bid, len(rows)))
        return len(rows)

    pipeline._db.merge_creditors = fake_merge  # type: ignore[method-assign]
    pipeline._backfill_creditor_merge(bankruptcy_id=bankruptcy_id, response=response)

    assert merge_calls == [(bankruptcy_id, 1)]


def test_backfill_creditor_merge_skips_manual_review() -> None:
    pipeline = DocumentPipeline()
    pipeline._db._enabled = True
    merge_calls: list[UUID] = []

    def fake_merge(bid: UUID, _rows: list[CreditorRow], **_: object) -> int:
        merge_calls.append(bid)
        return 0

    pipeline._db.merge_creditors = fake_merge  # type: ignore[method-assign]
    pipeline._backfill_creditor_merge(
        bankruptcy_id=uuid4(),
        response=ParseDocumentResponse(
            status="completed",
            filing_type=FilingType.CREDITOR_MATRIX,
            parse_mode=ParseMode.STRUCTURED,
            ocr_used=False,
            page_count=1,
            confidence=0.5,
            manual_review_required=True,
            creditors=[CreditorRow(creditor_name="Acme Corp")],
            validation=ValidationResult(
                confidence_score=0.5,
                manual_review_required=True,
            ),
        ),
    )
    assert merge_calls == []


def test_backfill_creditor_merge_swallows_merge_errors() -> None:
    pipeline = DocumentPipeline()
    pipeline._db._enabled = True

    def failing_merge(_bid: UUID, _rows: list[CreditorRow], **_: object) -> int:
        raise RuntimeError("RPC au_group_merge_creditor_matrix failed")

    pipeline._db.merge_creditors = failing_merge  # type: ignore[method-assign]
    pipeline._backfill_creditor_merge(
        bankruptcy_id=uuid4(),
        response=ParseDocumentResponse(
            status="completed",
            filing_type=FilingType.CREDITOR_MATRIX,
            parse_mode=ParseMode.STRUCTURED,
            ocr_used=False,
            page_count=1,
            confidence=0.92,
            manual_review_required=False,
            creditors=[CreditorRow(creditor_name="Acme Corp")],
            validation=ValidationResult(
                confidence_score=0.92,
                manual_review_required=False,
            ),
        ),
    )
