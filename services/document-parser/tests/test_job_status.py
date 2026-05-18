from uuid import uuid4

from app.pipeline.router import DocumentPipeline


def test_validation_from_cached_row_uses_persisted_flags() -> None:
    pipeline = DocumentPipeline()
    row = {
        "filing_type": "FORM_201",
        "parse_mode": "structured",
        "ocr_used": False,
        "page_count": 2,
        "raw_extraction": {
            "validation": {
                "confidence_score": 0.72,
                "manual_review_required": True,
                "missing_fields": ["industry_code"],
                "level": "medium",
            },
            "manual_review_required": True,
        },
    }
    validation = pipeline._validation_from_cached_row(row, pipeline._coerce_mapping(row["raw_extraction"]))
    assert validation.manual_review_required is True
    assert validation.confidence_score == 0.72


def test_build_job_status_manual_review_from_queue(monkeypatch) -> None:
    pipeline = DocumentPipeline()
    document_id = uuid4()

    def fake_get_document(_: object) -> dict:
        return {
            "id": str(document_id),
            "parser_version": "0.1.0",
            "filing_type": "FORM_201",
            "raw_extraction": {"ocr_confidence": 0.95},
        }

    def fake_has_pending(_: object) -> bool:
        return True

    monkeypatch.setattr(pipeline, "get_document_status", fake_get_document)
    monkeypatch.setattr(pipeline._db, "has_pending_manual_review", fake_has_pending)

    status = pipeline.build_job_status(document_id)
    assert status is not None
    assert status.manual_review_required is True
