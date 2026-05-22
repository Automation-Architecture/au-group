"""Unit tests for extract_form201 re-parse and validation fallback behavior."""

from types import MethodType
from uuid import uuid4

import pytest
from app.core.exceptions import DocumentProcessingError
from app.models.schemas import (
    FilingType,
    Form201Data,
    ParseDocumentResponse,
    ParseMode,
    ValidationResult,
)
from app.pipeline.router import DocumentPipeline
from app.validation.engine import validate_form201


def _parse_document_tuple(response: ParseDocumentResponse) -> tuple:
    return response, False, None, None, None, False


def _form201_response(
    *,
    form201: Form201Data | None,
    validation: ValidationResult | None = None,
    ocr_used: bool = False,
) -> ParseDocumentResponse:
    return ParseDocumentResponse(
        status="completed",
        filing_type=FilingType.FORM_201,
        parse_mode=ParseMode.STRUCTURED,
        ocr_used=ocr_used,
        page_count=1,
        confidence=0.0,
        manual_review_required=False,
        document_id=uuid4(),
        form201=form201,
        validation=validation,
    )


@pytest.fixture
def pipeline(monkeypatch: pytest.MonkeyPatch) -> DocumentPipeline:
    monkeypatch.setattr(
        DocumentPipeline,
        "__init__",
        lambda self: None,
    )
    return DocumentPipeline()


class TestExtractForm201Reparse:
    def test_reparses_when_form201_missing(self, pipeline: DocumentPipeline) -> None:
        form201 = Form201Data(debtor_name="Acme Corp", state="TX")
        first = _form201_response(form201=None)
        second = _form201_response(form201=form201)
        calls: list[dict] = []

        def fake_parse_document(self, **kwargs: object) -> tuple:
            calls.append(dict(kwargs))
            if len(calls) == 1:
                return _parse_document_tuple(first)
            return _parse_document_tuple(second)

        pipeline.parse_document = MethodType(fake_parse_document, pipeline)

        response = pipeline.extract_form201(
            bankruptcy_id=uuid4(),
            s3_key="raw-documents/1/form201.pdf",
        )

        assert len(calls) == 2
        assert calls[0]["force"] is False
        assert calls[1]["force"] is True
        assert response.form201.debtor_name == "Acme Corp"

    def test_skips_reparse_when_form201_present_validation_none(
        self, pipeline: DocumentPipeline
    ) -> None:
        form201 = Form201Data(debtor_name="Acme Corp", state="TX")
        result = _form201_response(form201=form201, validation=None)
        calls: list[dict] = []

        def fake_parse_document(self, **kwargs: object) -> tuple:
            calls.append(dict(kwargs))
            return _parse_document_tuple(result)

        pipeline.parse_document = MethodType(fake_parse_document, pipeline)

        response = pipeline.extract_form201(
            bankruptcy_id=uuid4(),
            s3_key="raw-documents/1/form201.pdf",
        )

        assert len(calls) == 1
        expected = validate_form201(form201, ocr_used=False)
        assert response.validation.confidence_score == expected.confidence_score
        assert response.validation.manual_review_required == expected.manual_review_required
        assert response.validation.missing_fields == expected.missing_fields

    def test_raises_when_still_processing(self, pipeline: DocumentPipeline) -> None:
        document_id = uuid4()
        processing = ParseDocumentResponse(
            status="processing",
            document_id=document_id,
            manual_review_required=False,
        )
        calls: list[dict] = []

        def fake_parse_document(self, **kwargs: object) -> tuple:
            calls.append(dict(kwargs))
            return _parse_document_tuple(processing)

        pipeline.parse_document = MethodType(fake_parse_document, pipeline)

        with pytest.raises(DocumentProcessingError, match="still processing"):
            pipeline.extract_form201(
                bankruptcy_id=uuid4(),
                s3_key="raw-documents/1/form201.pdf",
            )

        assert len(calls) == 1

    def test_raises_when_still_no_form201_after_refresh(self, pipeline: DocumentPipeline) -> None:
        empty = _form201_response(form201=None)

        def fake_parse_document(self, **kwargs: object) -> tuple:
            return _parse_document_tuple(empty)

        pipeline.parse_document = MethodType(fake_parse_document, pipeline)

        with pytest.raises(ValueError, match="did not return form201 data"):
            pipeline.extract_form201(
                bankruptcy_id=uuid4(),
                s3_key="raw-documents/1/bad.pdf",
            )
