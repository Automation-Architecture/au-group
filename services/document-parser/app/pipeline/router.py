import json
import logging
from pathlib import Path
from uuid import UUID, uuid4

from app.classifiers.filing_type import classify_filing_type
from app.core.config import get_settings
from app.extractors.creditor_matrix import extract_creditor_matrix
from app.extractors.form201 import extract_form201
from app.extractors.structured_pdf import StructuredPdfResult, extract_structured_pdf, probe_text_density
from app.models.schemas import (
    CreditorRow,
    ExtractCreditorMatrixResponse,
    ExtractForm201Response,
    FilingType,
    Form201Data,
    JobStatusResponse,
    ParseDocumentResponse,
    ParseMode,
    ParseTextResponse,
    ValidationResult,
)
from app.ocr.tesseract_engine import TesseractOcrEngine
from app.persistence.s3 import S3Client
from app.persistence.supabase import SupabaseClient
from app.validation.engine import (
    should_review_for_error,
    validate_creditor_matrix,
    validate_form201,
)

logger = logging.getLogger(__name__)


class DocumentPipeline:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._s3 = S3Client()
        self._db = SupabaseClient()
        self._ocr = TesseractOcrEngine()

    def _resolve_pdf(self, *, s3_key: str | None, document_url: str | None) -> tuple[Path, str]:
        if s3_key:
            return self._s3.download_to_temp(s3_key), s3_key
        if document_url:
            if document_url.startswith("file://"):
                if not self._settings.allow_local_file_urls:
                    raise ValueError("file:// URLs are disabled in this environment")
                path = Path(document_url.removeprefix("file://")).resolve()
                return path, str(path)
            raise ValueError("only file:// URLs are supported for document_url")
        raise ValueError("s3_key or document_url is required")

    def _choose_parse_mode(self, path: Path) -> ParseMode:
        page_count, coverage = probe_text_density(
            path, self._settings.structured_text_min_chars
        )
        if page_count > self._settings.max_pdf_pages:
            raise ValueError(f"PDF exceeds max pages ({self._settings.max_pdf_pages})")
        if coverage >= self._settings.structured_page_coverage:
            return ParseMode.STRUCTURED
        return ParseMode.OCR

    def _extract_text(
        self, path: Path, parse_mode: ParseMode
    ) -> tuple[str, int, bool, float, StructuredPdfResult | None]:
        if parse_mode == ParseMode.STRUCTURED:
            structured = extract_structured_pdf(path)
            return structured.text, structured.page_count, False, 1.0, structured
        ocr_result = self._ocr.extract_from_pdf(str(path))
        return (
            ocr_result.text,
            ocr_result.page_count,
            True,
            ocr_result.average_confidence,
            None,
        )

    def parse_structured(
        self,
        *,
        s3_key: str | None,
        document_url: str | None,
    ) -> ParseTextResponse:
        path, _key = self._resolve_pdf(s3_key=s3_key, document_url=document_url)
        try:
            structured = extract_structured_pdf(path)
            return ParseTextResponse(
                text=structured.text,
                page_count=structured.page_count,
                ocr_used=False,
                confidence=1.0,
                parse_mode=ParseMode.STRUCTURED,
            )
        finally:
            if s3_key:
                path.unlink(missing_ok=True)

    def parse_ocr(
        self,
        *,
        s3_key: str | None,
        document_url: str | None,
        bankruptcy_id: UUID | None = None,
    ) -> ParseTextResponse:
        path, key = self._resolve_pdf(s3_key=s3_key, document_url=document_url)
        try:
            ocr_result = self._ocr.extract_from_pdf(str(path))
            if bankruptcy_id and s3_key:
                bankruptcy = self._db.get_bankruptcy(bankruptcy_id)
                case_number = bankruptcy["case_number"] if bankruptcy else "unknown"
                self._s3.put_text(
                    self._s3.ocr_output_key(case_number, str(uuid4())),
                    ocr_result.text,
                )
            return ParseTextResponse(
                text=ocr_result.text,
                page_count=ocr_result.page_count,
                ocr_used=True,
                confidence=ocr_result.average_confidence,
                parse_mode=ParseMode.OCR,
            )
        finally:
            if s3_key:
                path.unlink(missing_ok=True)

    def extract_form201(
        self,
        *,
        bankruptcy_id: UUID,
        s3_key: str,
        docket_hint: FilingType | None = None,
        force: bool = False,
    ) -> ExtractForm201Response:
        result = self.parse_document(
            bankruptcy_id=bankruptcy_id,
            s3_key=s3_key,
            docket_hint=docket_hint or FilingType.FORM_201,
            force=force,
        )
        if result.form201 is None or result.validation is None:
            refreshed_result = self.parse_document(
                bankruptcy_id=bankruptcy_id,
                s3_key=s3_key,
                docket_hint=docket_hint or FilingType.FORM_201,
                force=True,
            )
            if refreshed_result.form201 is not None or refreshed_result.validation is not None:
                result = refreshed_result

        form201 = result.form201
        if form201 is None:
            raise ValueError("parse_document() did not return form201 data")

        validation = result.validation or validate_form201(form201, ocr_used=result.ocr_used)
        return ExtractForm201Response(
            filing_type=result.filing_type,
            form201=form201,
            validation=validation,
            document_id=result.document_id,
        )

    def extract_creditor_matrix(
        self,
        *,
        bankruptcy_id: UUID,
        s3_key: str,
        docket_hint: FilingType | None = None,
        force: bool = False,
    ) -> ExtractCreditorMatrixResponse:
        result = self.parse_document(
            bankruptcy_id=bankruptcy_id,
            s3_key=s3_key,
            docket_hint=docket_hint or FilingType.CREDITOR_MATRIX,
            force=force,
        )
        creditors = result.creditors or []
        validation = result.validation or validate_creditor_matrix(creditors)
        return ExtractCreditorMatrixResponse(
            filing_type=result.filing_type,
            creditors=creditors,
            validation=validation,
            document_id=result.document_id,
            creditor_count=len(creditors),
        )

    def parse_document(
        self,
        *,
        bankruptcy_id: UUID | None,
        s3_key: str | None,
        document_url: str | None = None,
        docket_hint: FilingType | None = None,
        force: bool = False,
    ) -> ParseDocumentResponse:
        path, key = self._resolve_pdf(s3_key=s3_key, document_url=document_url)
        try:
            content_hash = S3Client.sha256_file(path)
            if not force:
                existing = self._db.find_document_by_hash(
                    content_hash, self._settings.parser_version
                )
                if existing:
                    return self._response_from_cached_row(existing)

            parse_mode = self._choose_parse_mode(path)
            text, page_count, ocr_used, ocr_confidence, structured = self._extract_text(
                path, parse_mode
            )
            filing_type = classify_filing_type(text, docket_hint=docket_hint)

            form201 = None
            creditors = None
            if filing_type == FilingType.FORM_201:
                form201 = extract_form201(text, structured)
                validation = validate_form201(form201, ocr_used=ocr_used)
            elif filing_type == FilingType.CREDITOR_MATRIX:
                creditors = extract_creditor_matrix(text, structured)
                validation = validate_creditor_matrix(creditors)
            else:
                validation = should_review_for_error("unknown_filing_type")

            document_id = uuid4()
            bankruptcy = (
                self._db.get_bankruptcy(bankruptcy_id) if bankruptcy_id else None
            )
            case_number = bankruptcy["case_number"] if bankruptcy else "unknown"

            if ocr_used:
                self._s3.put_text(
                    self._s3.ocr_output_key(case_number, str(document_id)),
                    text,
                )

            parsed_key = self._s3.parsed_output_key(case_number, str(document_id))
            self._s3.put_json(
                parsed_key,
                json.dumps(
                    {
                        "filing_type": filing_type.value,
                        "form201": form201.model_dump() if form201 else None,
                        "creditors": [c.model_dump() for c in creditors]
                        if creditors
                        else None,
                        "validation": validation.model_dump(),
                    }
                ),
            )

            doc_payload = SupabaseClient.document_payload(
                bankruptcy_id=bankruptcy_id,
                s3_key=key,
                content_sha256=content_hash,
                page_count=page_count,
                filing_type=filing_type,
                parse_mode=parse_mode,
                ocr_used=ocr_used,
                parser_version=self._settings.parser_version,
                raw_extraction={
                    "text_preview": text[:2000],
                    "filing_type": filing_type.value,
                    "ocr_confidence": ocr_confidence,
                    "parsed_s3_key": parsed_key,
                    "validation": validation.model_dump(),
                    "manual_review_required": validation.manual_review_required,
                    "form201": form201.model_dump() if form201 else None,
                    "creditors": [c.model_dump() for c in creditors] if creditors else None,
                },
            )
            doc_payload["id"] = str(document_id)
            saved = self._db.upsert_document(doc_payload)
            if saved.get("id"):
                document_id = UUID(str(saved["id"]))

            if form201 and bankruptcy_id:
                self._db.insert_form201_extraction(
                    SupabaseClient.form201_to_row(
                        document_id,
                        bankruptcy_id,
                        form201,
                        validation.confidence_score,
                        validation.manual_review_required,
                        form201.model_dump(),
                        self._settings.parser_version,
                    )
                )
                self._db.upsert_bankruptcy_from_form201(
                    bankruptcy_id,
                    form201,
                    validation.confidence_score,
                    validation.manual_review_required,
                )

            if creditors and bankruptcy_id:
                extraction_id = uuid4()
                self._db.insert_creditor_matrix_extraction(
                    {
                        "id": str(extraction_id),
                        "document_id": str(document_id),
                        "bankruptcy_id": str(bankruptcy_id),
                        "creditor_count": len(creditors),
                        "confidence_score": validation.confidence_score,
                        "manual_review_required": validation.manual_review_required,
                        "parser_version": self._settings.parser_version,
                    }
                )
                self._db.insert_creditor_matrix_rows(
                    [
                        {
                            "extraction_id": str(extraction_id),
                            "creditor_name": row.creditor_name,
                            "address": row.address,
                            "claim_amount": row.claim_amount,
                            "entity_type": row.entity_type,
                        }
                        for row in creditors
                    ]
                )
                if not validation.manual_review_required:
                    self._db.merge_creditors(bankruptcy_id, creditors)

            if validation.manual_review_required:
                self._db.insert_manual_review(
                    {
                        "bankruptcy_id": str(bankruptcy_id) if bankruptcy_id else None,
                        "document_id": str(document_id),
                        "review_reason": ",".join(validation.missing_fields)
                        or "low_confidence",
                        "status": "pending",
                    }
                )

            confidence = validation.confidence_score
            if ocr_used:
                confidence = min(confidence, ocr_confidence)

            return ParseDocumentResponse(
                filing_type=filing_type,
                parse_mode=parse_mode,
                ocr_used=ocr_used,
                page_count=page_count,
                confidence=confidence,
                manual_review_required=validation.manual_review_required,
                document_id=document_id,
                form201=form201,
                creditors=creditors,
                validation=validation,
            )
        finally:
            if s3_key:
                path.unlink(missing_ok=True)

    def _coerce_mapping(self, value: object) -> dict:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except (TypeError, ValueError, json.JSONDecodeError):
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}

    def _validation_from_cached_row(self, row: dict, raw: dict) -> ValidationResult:
        validation_data = self._coerce_mapping(row.get("validation"))
        if not validation_data:
            validation_data = self._coerce_mapping(raw.get("validation"))

        missing_fields = validation_data.get("missing_fields")
        if not isinstance(missing_fields, list):
            missing_fields = []

        manual_review_required = validation_data.get("manual_review_required")
        if manual_review_required is None:
            manual_review_required = row.get("manual_review_required")
        if manual_review_required is None:
            manual_review_required = raw.get("manual_review_required")

        confidence_score = validation_data.get("confidence_score")
        if confidence_score is None:
            confidence_score = raw.get("ocr_confidence")
        if confidence_score is None:
            confidence_score = 1.0

        level = validation_data.get("level")
        if level is None:
            level = "high" if float(confidence_score) >= 0.9 else "medium"

        return ValidationResult(
            confidence_score=float(confidence_score),
            manual_review_required=bool(manual_review_required),
            missing_fields=missing_fields,
            level=level,
        )

    def _form201_from_raw(self, raw: dict) -> Form201Data | None:
        data = self._coerce_mapping(raw.get("form201"))
        if not data:
            return None
        return Form201Data.model_validate(data)

    def _creditors_from_raw(self, raw: dict) -> list[CreditorRow] | None:
        items = raw.get("creditors")
        if not isinstance(items, list):
            return None
        return [CreditorRow.model_validate(item) for item in items]

    def _response_from_cached_row(self, row: dict) -> ParseDocumentResponse:
        raw = self._coerce_mapping(row.get("raw_extraction"))
        validation = self._validation_from_cached_row(row, raw)
        document_id = UUID(str(row["id"])) if row.get("id") else None
        if document_id and self._db.has_pending_manual_review(document_id):
            validation = validation.model_copy(update={"manual_review_required": True})
        return ParseDocumentResponse(
            filing_type=FilingType(row.get("filing_type", FilingType.UNKNOWN.value)),
            parse_mode=ParseMode(row.get("parse_mode", ParseMode.STRUCTURED.value)),
            ocr_used=bool(row.get("ocr_used")),
            page_count=int(row.get("page_count") or 0),
            confidence=float(validation.confidence_score),
            manual_review_required=bool(validation.manual_review_required),
            document_id=document_id,
            form201=self._form201_from_raw(raw),
            creditors=self._creditors_from_raw(raw),
            validation=validation,
        )

    def get_document_status(self, document_id: UUID) -> dict | None:
        return self._db.get_document(document_id)

    def build_job_status(self, document_id: UUID) -> JobStatusResponse | None:
        row = self.get_document_status(document_id)
        if not row:
            return None
        raw = self._coerce_mapping(row.get("raw_extraction"))
        validation = self._validation_from_cached_row(row, raw)
        if self._db.has_pending_manual_review(document_id):
            validation = validation.model_copy(update={"manual_review_required": True})
        filing = row.get("filing_type")
        return JobStatusResponse(
            document_id=document_id,
            status="completed" if raw else "pending",
            parser_version=str(row.get("parser_version", "")),
            filing_type=FilingType(filing) if filing else None,
            manual_review_required=validation.manual_review_required,
            result=raw if raw else None,
        )

    def list_review_queue(
        self, *, limit: int = 50, offset: int = 0, status: str | None = None
    ) -> tuple[list[dict], int]:
        return self._db.list_manual_review(limit=limit, offset=offset, status=status)
