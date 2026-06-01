from uuid import uuid4

from app.pipeline.job_status import (
    JOB_STATUS_PROCESSING,
    job_status_from_raw,
    mark_raw_completed,
    processing_placeholder_raw,
)
from app.pipeline.router import DocumentPipeline


def test_job_status_from_processing_placeholder() -> None:
    raw = processing_placeholder_raw()
    assert job_status_from_raw(raw) == JOB_STATUS_PROCESSING


def test_mark_raw_completed_sets_status() -> None:
    completed = mark_raw_completed({"debtor_name": "Acme"})
    assert completed["job_status"] == "completed"
    assert completed["debtor_name"] == "Acme"


def test_response_from_cached_processing_row() -> None:
    pipeline = DocumentPipeline()
    document_id = uuid4()
    row = {
        "id": str(document_id),
        "filing_type": "UNKNOWN",
        "parse_mode": "structured",
        "ocr_used": False,
        "page_count": 0,
        "raw_extraction": processing_placeholder_raw(),
    }
    response = pipeline._response_from_cached_row(row)
    assert response.status == "processing"
    assert response.document_id == document_id


def test_build_job_status_failed() -> None:
    pipeline = DocumentPipeline()
    document_id = uuid4()
    row = {
        "id": str(document_id),
        "parser_version": "0.1.0",
        "filing_type": "FORM_201",
        "raw_extraction": {
            "job_status": "failed",
            "job_error": "OCR timeout",
        },
    }

    def fake_get_document(_: object) -> dict:
        return row

    pipeline.get_document_status = fake_get_document  # type: ignore[method-assign]
    status = pipeline.build_job_status(document_id)
    assert status is not None
    assert status.status == "failed"
    assert status.error == "OCR timeout"


def test_build_job_status_dedupes_creditors_in_result() -> None:
    pipeline = DocumentPipeline()
    document_id = uuid4()
    raw = mark_raw_completed(
        {
            "filing_type": "CREDITOR_MATRIX",
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
    )
    row = {
        "id": str(document_id),
        "parser_version": "0.1.0",
        "filing_type": "CREDITOR_MATRIX",
        "parse_mode": "structured",
        "ocr_used": False,
        "page_count": 1,
        "raw_extraction": raw,
    }

    def fake_get_document(_: object) -> dict:
        return row

    pipeline.get_document_status = fake_get_document  # type: ignore[method-assign]
    status = pipeline.build_job_status(document_id)
    assert status is not None
    assert status.result is not None
    assert len(status.result["creditors"]) == 1
    assert status.result["creditors"][0]["claim_amount"] == 150.0
