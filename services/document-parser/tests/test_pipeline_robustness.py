import logging
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
from app.pipeline.job_status import RAW_CREDITORS_MERGED, processing_placeholder_raw
from app.persistence.supabase import SupabaseClient
from app.pipeline.router import DocumentPipeline
from tests.helpers.fake_supabase import FakeSupabaseClient


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


def test_dedup_creditors_if_enabled_disabled_returns_unchanged() -> None:
    pipeline = DocumentPipeline()
    pipeline._settings = pipeline._settings.model_copy(update={"creditor_dedup_enabled": False})
    creditors = [
        CreditorRow(creditor_name="ABC Corp", address="123 Main St", claim_amount=100.0),
        CreditorRow(creditor_name="ABC Corporation", address="123 Main St", claim_amount=50.0),
    ]
    out, stats = pipeline._dedup_creditors_if_enabled(creditors)
    assert len(out) == 2
    assert stats is None


def test_dedup_creditors_if_enabled_empty_list() -> None:
    pipeline = DocumentPipeline()
    out, stats = pipeline._dedup_creditors_if_enabled([])
    assert out == []
    assert stats is None


def test_with_deduped_creditors_schedule_filing_dedupes() -> None:
    pipeline = DocumentPipeline()
    response = ParseDocumentResponse(
        status="completed",
        filing_type=FilingType.SCHEDULE,
        parse_mode=ParseMode.STRUCTURED,
        ocr_used=False,
        page_count=1,
        confidence=0.92,
        manual_review_required=False,
        creditors=[
            CreditorRow(creditor_name="ABC Corp", address="123 Main St", claim_amount=100.0),
            CreditorRow(creditor_name="ABC Corporation", address="123 Main St", claim_amount=50.0),
        ],
    )
    out = pipeline._with_deduped_creditors(response)
    assert out.filing_type == FilingType.SCHEDULE
    assert out.creditors is not None
    assert len(out.creditors) == 1
    assert out.creditors[0].claim_amount == pytest.approx(150.0)


def test_sync_cached_raw_extraction_persists_dedup_for_schedule_filing() -> None:
    FakeSupabaseClient._documents.clear()
    fake_db = FakeSupabaseClient()
    pipeline = DocumentPipeline()
    pipeline._db = fake_db  # type: ignore[assignment]
    content_hash = "feedface" * 8
    document_id = uuid4()
    raw = {
        "job_status": "completed",
        "creditors": [
            {"creditor_name": "ABC Corp", "address": "123 Main St", "claim_amount": 100.0},
            {"creditor_name": "ABC Corporation", "address": "123 Main St", "claim_amount": 50.0},
        ],
    }
    fake_db.upsert_document(
        SupabaseClient.document_payload(
            bankruptcy_id=None,
            s3_key="raw-documents/test/schedule.pdf",
            content_sha256=content_hash,
            page_count=1,
            filing_type=FilingType.SCHEDULE,
            parse_mode=ParseMode.STRUCTURED,
            ocr_used=False,
            parser_version=pipeline._settings.parser_version,
            raw_extraction=raw,
        )
        | {"id": str(document_id)}
    )

    pipeline._sync_cached_matrix_raw_extraction(content_hash)
    stored = fake_db.get_document(document_id)["raw_extraction"]
    assert stored.get("dedup_stats", {}).get("deduped_count") == 1
    assert len(stored.get("creditors") or []) == 1


def test_with_deduped_creditors_no_creditors_returns_unchanged() -> None:
    pipeline = DocumentPipeline()
    response = ParseDocumentResponse(
        status="completed",
        filing_type=FilingType.CREDITOR_MATRIX,
        parse_mode=ParseMode.STRUCTURED,
        ocr_used=False,
        page_count=1,
        confidence=0.92,
        manual_review_required=False,
        creditors=None,
    )
    assert pipeline._with_deduped_creditors(response) is response


def test_backfill_creditor_merge_passes_deduped_creditors() -> None:
    pipeline = DocumentPipeline()
    pipeline._db._enabled = True
    bankruptcy_id = uuid4()
    response = ParseDocumentResponse(
        status="completed",
        filing_type=FilingType.CREDITOR_MATRIX,
        parse_mode=ParseMode.STRUCTURED,
        ocr_used=False,
        page_count=1,
        confidence=0.92,
        manual_review_required=False,
        creditors=[
            CreditorRow(
                creditor_name="ABC Corp",
                address="123 Main St",
                claim_amount=100.0,
            ),
            CreditorRow(
                creditor_name="ABC Corporation",
                address="123 Main St",
                claim_amount=50.0,
            ),
        ],
        validation=ValidationResult(
            confidence_score=0.92,
            manual_review_required=False,
        ),
    )
    merged_batches: list[list[CreditorRow]] = []

    def fake_merge(
        _bid: UUID,
        rows: list[CreditorRow],
        *,
        confidence_score: float | None = None,
    ) -> int:
        merged_batches.append(list(rows))
        return len(rows)

    pipeline._db.merge_creditors = fake_merge  # type: ignore[method-assign]
    pipeline._backfill_creditor_merge(bankruptcy_id=bankruptcy_id, response=response)

    assert len(merged_batches) == 1
    assert len(merged_batches[0]) == 1
    assert merged_batches[0][0].claim_amount == 150.0


def test_backfill_creditor_merge_skips_when_creditors_merged_flag_set() -> None:
    FakeSupabaseClient._documents.clear()
    pipeline = DocumentPipeline()
    pipeline._db = FakeSupabaseClient()  # type: ignore[assignment]
    pipeline._db._enabled = True
    document_id = uuid4()
    bankruptcy_id = uuid4()
    FakeSupabaseClient._documents[str(document_id)] = {
        "id": str(document_id),
        "raw_extraction": {"creditors_merged": True, "job_status": "completed"},
    }
    merge_calls: list[UUID] = []

    def fake_merge(bid: UUID, _rows: list[CreditorRow], **_: object) -> int:
        merge_calls.append(bid)
        return 0

    pipeline._db.merge_creditors = fake_merge  # type: ignore[method-assign]
    pipeline._backfill_creditor_merge(
        bankruptcy_id=bankruptcy_id,
        response=ParseDocumentResponse(
            status="completed",
            filing_type=FilingType.CREDITOR_MATRIX,
            parse_mode=ParseMode.STRUCTURED,
            ocr_used=False,
            page_count=1,
            confidence=0.92,
            manual_review_required=False,
            document_id=document_id,
            creditors=[CreditorRow(creditor_name="Acme Corp")],
            validation=ValidationResult(
                confidence_score=0.92,
                manual_review_required=False,
            ),
        ),
    )
    assert merge_calls == []


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


def test_with_deduped_creditors_merges_duplicates_for_api_response() -> None:
    pipeline = DocumentPipeline()
    creditors = [
        CreditorRow(
            creditor_name="ABC Corp",
            address="123 Main St",
            claim_amount=100.0,
            source_line_numbers=[1],
        ),
        CreditorRow(
            creditor_name="ABC Corporation",
            address="123 Main St",
            claim_amount=50.0,
            source_line_numbers=[2],
        ),
    ]
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
    refreshed = pipeline._with_deduped_creditors(response)
    assert len(refreshed.creditors or []) == 1
    assert refreshed.creditors[0].claim_amount == 150.0
    assert len(response.creditors or []) == 2


def test_backfill_creditor_merge_swallows_merge_errors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    pipeline = DocumentPipeline()
    pipeline._db._enabled = True
    merge_attempts = 0

    def failing_merge(_bid: UUID, _rows: list[CreditorRow], **_: object) -> int:
        nonlocal merge_attempts
        merge_attempts += 1
        raise RuntimeError("RPC au_group_merge_creditor_matrix failed")

    pipeline._db.merge_creditors = failing_merge  # type: ignore[method-assign]
    response = ParseDocumentResponse(
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
    )
    with caplog.at_level(logging.WARNING):
        pipeline._backfill_creditor_merge(bankruptcy_id=uuid4(), response=response)

    assert merge_attempts == 1
    assert len(response.creditors or []) == 1
    assert any(
        "creditor_merge_backfill_failed" in record.getMessage() for record in caplog.records
    )


def test_sync_cached_matrix_raw_extraction_skips_non_matrix_filing() -> None:
    FakeSupabaseClient._documents.clear()
    fake_db = FakeSupabaseClient()
    pipeline = DocumentPipeline()
    pipeline._db = fake_db  # type: ignore[assignment]
    content_hash = "cafebabe" * 8
    document_id = uuid4()
    raw = {
        "job_status": "completed",
        "creditors": [
            {"creditor_name": "ABC Corp", "address": "123 Main St", "claim_amount": 100.0},
            {"creditor_name": "ABC Corporation", "address": "123 Main St", "claim_amount": 50.0},
        ],
    }
    fake_db.upsert_document(
        SupabaseClient.document_payload(
            bankruptcy_id=None,
            s3_key="raw-documents/test/form201.pdf",
            content_sha256=content_hash,
            page_count=1,
            filing_type=FilingType.FORM_201,
            parse_mode=ParseMode.STRUCTURED,
            ocr_used=False,
            parser_version=pipeline._settings.parser_version,
            raw_extraction=raw,
        )
        | {"id": str(document_id)}
    )

    pipeline._sync_cached_matrix_raw_extraction(content_hash)
    stored = fake_db.get_document(document_id)["raw_extraction"]
    assert "dedup_stats" not in stored
    assert len(stored.get("creditors") or []) == 2


def test_sync_cached_matrix_raw_extraction_persists_dedup_stats() -> None:
    FakeSupabaseClient._documents.clear()
    fake_db = FakeSupabaseClient()
    pipeline = DocumentPipeline()
    pipeline._db = fake_db  # type: ignore[assignment]
    content_hash = "deadbeef" * 8
    document_id = uuid4()
    raw = {
        "job_status": "completed",
        "creditors": [
            {
                "creditor_name": "ABC Corp",
                "address": "123 Main St",
                "claim_amount": 100.0,
            },
            {
                "creditor_name": "ABC Corporation",
                "address": "123 Main St",
                "claim_amount": 50.0,
            },
        ],
    }
    fake_db.upsert_document(
        SupabaseClient.document_payload(
            bankruptcy_id=None,
            s3_key="raw-documents/test/matrix.pdf",
            content_sha256=content_hash,
            page_count=1,
            filing_type=FilingType.CREDITOR_MATRIX,
            parse_mode=ParseMode.STRUCTURED,
            ocr_used=False,
            parser_version=pipeline._settings.parser_version,
            raw_extraction=raw,
        )
        | {"id": str(document_id)}
    )

    pipeline._sync_cached_matrix_raw_extraction(content_hash)
    stored = fake_db.get_document(document_id)["raw_extraction"]
    assert stored.get("dedup_stats", {}).get("deduped_count") == 1
    assert len(stored.get("creditors") or []) == 1
    assert stored["creditors"][0]["claim_amount"] == 150.0


def test_dedup_creditors_if_enabled_logs_when_duplicates_removed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    pipeline = DocumentPipeline()
    creditors = [
        CreditorRow(creditor_name="ABC Corp", address="123 Main St", claim_amount=100.0),
        CreditorRow(creditor_name="ABC Corporation", address="123 Main St", claim_amount=50.0),
    ]
    with caplog.at_level(logging.INFO):
        _, stats = pipeline._dedup_creditors_if_enabled(creditors)
    assert stats is not None
    assert stats["duplicates_removed"] == 1
    assert any("creditor_dedup" in record.getMessage() for record in caplog.records)
