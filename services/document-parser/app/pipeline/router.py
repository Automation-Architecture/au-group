import json
import logging
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from uuid import UUID, uuid4

from app.classifiers.filing_type import classify_filing_type
from app.core.config import get_settings
from app.core.exceptions import (
    BackgroundJobBusyError,
    BankruptcyIdRequiredError,
    BankruptcyNotFoundError,
    DocumentProcessingError,
)
from app.core.logging import log_event
from app.core.request_context import bind_request_id, reset_request_id
from app.core.s3_validation import validate_s3_key
from app.core.url_safety import download_url_to_path
from app.extractors.creditor_matrix import extract_creditor_matrix
from app.extractors.form201 import extract_form201
from app.extractors.structured_pdf import (
    StructuredPdfResult,
    extract_structured_pdf,
    probe_text_density,
)
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
from app.pipeline.background_jobs import release_background_slot, try_acquire_background_slot
from app.pipeline.job_status import (
    JOB_STATUS_FAILED,
    JOB_STATUS_PROCESSING,
    failed_job_raw,
    job_status_from_raw,
    mark_raw_completed,
    processing_placeholder_raw,
)
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

    def _require_bankruptcy(self, bankruptcy_id: UUID | None) -> None:
        if bankruptcy_id is None or not self._db._enabled:
            return
        if self._db.get_bankruptcy(bankruptcy_id) is None:
            raise BankruptcyNotFoundError(bankruptcy_id)

    def _backfill_creditor_merge(
        self,
        *,
        bankruptcy_id: UUID | None,
        response: ParseDocumentResponse,
    ) -> None:
        """Merge cached matrix creditors into creditors / bankruptcy_creditors when RPC was skipped."""
        if (
            not self._db._enabled
            or bankruptcy_id is None
            or not response.creditors
            or response.manual_review_required
            or response.validation is None
        ):
            return
        try:
            merged = self._db.merge_creditors(
                bankruptcy_id,
                response.creditors,
                confidence_score=response.validation.confidence_score,
            )
            log_event(
                logger,
                "creditor_merge_backfill",
                bankruptcy_id=str(bankruptcy_id),
                merged_count=merged,
            )
        except Exception as exc:
            logger.warning(
                "creditor_merge_backfill_failed bankruptcy_id=%s: %s",
                bankruptcy_id,
                exc,
            )

    def _download_http_to_temp(self, document_url: str) -> Path:
        parsed = urlparse(document_url)
        suffix = Path(parsed.path).suffix or ".pdf"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp_path = Path(tmp.name)
        tmp.close()
        settings = self._settings
        try:
            download_url_to_path(
                document_url,
                tmp_path,
                max_bytes=settings.max_download_bytes,
                timeout_sec=settings.http_download_timeout_sec,
                max_redirects=settings.http_max_redirects,
                allow_document_url=settings.allow_document_url,
                allowed_host_suffixes=settings.download_host_suffixes,
                require_https=settings.require_https_downloads,
            )
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise
        return tmp_path

    def _resolve_pdf(self, *, s3_key: str | None, document_url: str | None) -> tuple[Path, str]:
        if s3_key:
            validate_s3_key(s3_key, operation="read")
            return self._s3.download_to_temp(s3_key), s3_key
        if document_url:
            if document_url.startswith("file://"):
                if not self._settings.allow_local_file_urls:
                    raise ValueError("file:// URLs are disabled in this environment")
                if self._settings.is_production:
                    raise ValueError("file:// URLs are disabled in production")
                root = self._settings.local_file_root
                if not root:
                    raise ValueError("LOCAL_FILE_ROOT must be set when file:// URLs are enabled")
                path = Path(document_url.removeprefix("file://")).resolve()
                root_path = Path(root).resolve()
                try:
                    path.relative_to(root_path)
                except ValueError as exc:
                    raise ValueError("Local file path is outside allowed directory") from exc
                if not path.is_file():
                    raise FileNotFoundError("Local file not found")
                return path, str(path)
            if document_url.startswith(("http://", "https://")):
                path = self._download_http_to_temp(document_url)
                return path, document_url
        raise ValueError("s3_key or document_url is required")

    @staticmethod
    def _should_unlink_temp(*, s3_key: str | None, document_url: str | None) -> bool:
        if s3_key:
            return True
        return bool(document_url and document_url.startswith(("http://", "https://")))

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
            if self._should_unlink_temp(s3_key=s3_key, document_url=document_url):
                path.unlink(missing_ok=True)

    def parse_ocr(
        self,
        *,
        s3_key: str | None,
        document_url: str | None,
        bankruptcy_id: UUID | None = None,
    ) -> ParseTextResponse:
        self._require_bankruptcy(bankruptcy_id)
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
            if self._should_unlink_temp(s3_key=s3_key, document_url=document_url):
                path.unlink(missing_ok=True)

    @staticmethod
    def _validation_for_form201(
        result: ParseDocumentResponse, form201: Form201Data
    ) -> ValidationResult:
        if result.validation is not None:
            return result.validation
        return validate_form201(form201, ocr_used=result.ocr_used)

    @staticmethod
    def _validation_for_creditor_matrix(
        result: ParseDocumentResponse, creditors: list[CreditorRow]
    ) -> ValidationResult:
        if result.validation is not None:
            return result.validation
        return validate_creditor_matrix(creditors)

    def extract_form201(
        self,
        *,
        bankruptcy_id: UUID,
        s3_key: str,
        docket_hint: FilingType | None = None,
        force: bool = False,
    ) -> ExtractForm201Response:
        result, _, _, _, _, _ = self.parse_document(
            bankruptcy_id=bankruptcy_id,
            s3_key=s3_key,
            docket_hint=docket_hint or FilingType.FORM_201,
            force=force,
        )
        if result.status == "processing":
            if result.document_id is None:
                raise DocumentProcessingError(
                    "Document is still processing; poll job status before extract/form201"
                )
            raise DocumentProcessingError(
                "Document is still processing; poll GET /api/v1/jobs/"
                f"{result.document_id} before calling POST /api/v1/extract/form201"
            )
        # Re-parse only when extraction is missing (mis-classified filing, empty extract,
        # or cache without form201 in raw_extraction). Validation is always derived on read
        # via _validation_from_cached_row or _validation_for_form201; do not force re-parse
        # for missing validation alone.
        if result.form201 is None:
            refreshed_result, _, _, _, _, _ = self.parse_document(
                bankruptcy_id=bankruptcy_id,
                s3_key=s3_key,
                docket_hint=docket_hint or FilingType.FORM_201,
                force=True,
            )
            if refreshed_result.form201 is not None:
                result = refreshed_result

        form201 = result.form201
        if form201 is None:
            raise ValueError("parse_document() did not return form201 data")

        validation = self._validation_for_form201(result, form201)
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
        result, _, _, _, _, _ = self.parse_document(
            bankruptcy_id=bankruptcy_id,
            s3_key=s3_key,
            docket_hint=docket_hint or FilingType.CREDITOR_MATRIX,
            force=force,
        )
        if result.status == "processing":
            if result.document_id is None:
                raise DocumentProcessingError(
                    "Document is still processing; poll job status before extract/creditor-matrix"
                )
            raise DocumentProcessingError(
                "Document is still processing; poll GET /api/v1/jobs/"
                f"{result.document_id} before calling POST /api/v1/extract/creditor-matrix"
            )
        creditors = result.creditors or []
        validation = self._validation_for_creditor_matrix(result, creditors)
        return ExtractCreditorMatrixResponse(
            filing_type=result.filing_type,
            creditors=creditors,
            validation=validation,
            document_id=result.document_id,
            creditor_count=len(creditors),
        )

    def _resolve_document_id(
        self,
        *,
        document_id: UUID | None,
        content_hash: str,
    ) -> UUID:
        if document_id is not None:
            return document_id
        existing = self._db.find_document_by_hash(
            content_hash, self._settings.parser_version
        )
        if existing and existing.get("id"):
            return UUID(str(existing["id"]))
        return uuid4()

    def _lookup_cached_document(
        self,
        content_hash: str,
        *,
        force: bool,
        bankruptcy_id: UUID | None = None,
    ) -> ParseDocumentResponse | None:
        existing = self._db.find_document_by_hash(
            content_hash, self._settings.parser_version
        )
        if not existing:
            return None
        raw = self._coerce_mapping(existing.get("raw_extraction"))
        if job_status_from_raw(raw) == JOB_STATUS_PROCESSING:
            if force:
                raise DocumentProcessingError(
                    "Document is still processing; poll GET /api/v1/jobs/{document_id} "
                    "before forcing a re-parse"
                )
            return self._response_from_cached_row(existing)
        if not force:
            if bankruptcy_id and not existing.get("bankruptcy_id"):
                return None
            return self._response_from_cached_row(existing)
        if bankruptcy_id and not existing.get("bankruptcy_id"):
            return None
        return None

    def parse_document(
        self,
        *,
        bankruptcy_id: UUID | None,
        s3_key: str | None,
        document_url: str | None = None,
        docket_hint: FilingType | None = None,
        force: bool = False,
        async_mode: bool = False,
    ) -> tuple[ParseDocumentResponse, bool, Path | None, str | None, str | None, bool]:
        """Returns (response, schedule_background, temp_path, content_hash, key, release_slot)."""
        if self._settings.require_bankruptcy_id and bankruptcy_id is None:
            raise BankruptcyIdRequiredError()
        self._require_bankruptcy(bankruptcy_id)

        path, key = self._resolve_pdf(s3_key=s3_key, document_url=document_url)
        content_hash: str | None = None
        schedule_background = False
        release_slot = False
        try:
            content_hash = S3Client.sha256_file(path)
            cached = self._lookup_cached_document(
                content_hash, force=force, bankruptcy_id=bankruptcy_id
            )
            if cached is not None:
                self._backfill_creditor_merge(bankruptcy_id=bankruptcy_id, response=cached)
                return cached, False, None, None, None, False

            if async_mode and self._settings.async_parse_enabled:
                if not try_acquire_background_slot(self._settings.async_parse_max_concurrent):
                    raise BackgroundJobBusyError()
                release_slot = True
                document_id = self._resolve_document_id(
                    document_id=None, content_hash=content_hash
                )
                doc_payload = SupabaseClient.document_payload(
                    bankruptcy_id=bankruptcy_id,
                    s3_key=key,
                    content_sha256=content_hash,
                    page_count=0,
                    filing_type=FilingType.UNKNOWN,
                    parse_mode=ParseMode.STRUCTURED,
                    ocr_used=False,
                    parser_version=self._settings.parser_version,
                    raw_extraction=processing_placeholder_raw(),
                )
                doc_payload["id"] = str(document_id)
                saved = self._db.upsert_document(doc_payload)
                if saved.get("id"):
                    document_id = UUID(str(saved["id"]))
                schedule_background = True
                return (
                    self._processing_response(document_id=document_id),
                    True,
                    path,
                    content_hash,
                    key,
                    True,
                )

            result = self._parse_document_sync(
                path=path,
                key=key,
                content_hash=content_hash,
                bankruptcy_id=bankruptcy_id,
                docket_hint=docket_hint,
                force=force,
                document_id=None,
            )
            return result, False, None, None, None, False
        except Exception:
            if release_slot:
                release_background_slot(self._settings.async_parse_max_concurrent)
            if self._should_unlink_temp(s3_key=s3_key, document_url=document_url):
                path.unlink(missing_ok=True)
            raise
        finally:
            if not schedule_background and self._should_unlink_temp(
                s3_key=s3_key, document_url=document_url
            ):
                path.unlink(missing_ok=True)

    def run_parse_document_background(
        self,
        *,
        document_id: UUID,
        bankruptcy_id: UUID | None,
        s3_key: str | None,
        document_url: str | None,
        docket_hint: FilingType | None,
        temp_path: Path | None = None,
        content_hash: str | None = None,
        release_slot: bool = True,
        correlation_id: str | None = None,
    ) -> None:
        ctx_token = bind_request_id(correlation_id) if correlation_id else None
        path: Path | None = temp_path
        key = s3_key or document_url or ""
        try:
            self._require_bankruptcy(bankruptcy_id)
            if path is None or not path.is_file():
                path, key = self._resolve_pdf(s3_key=s3_key, document_url=document_url)
            hash_value = content_hash or S3Client.sha256_file(path)
            self._parse_document_sync(
                path=path,
                key=key,
                content_hash=hash_value,
                bankruptcy_id=bankruptcy_id,
                docket_hint=docket_hint,
                force=True,
                document_id=document_id,
            )
        except Exception as exc:
            log_event(
                logger,
                "background_parse_failed",
                document_id=str(document_id),
                error=str(exc),
            )
            self._mark_job_failed(document_id, str(exc))
        finally:
            if release_slot:
                release_background_slot(self._settings.async_parse_max_concurrent)
            if path and self._should_unlink_temp(s3_key=s3_key, document_url=document_url):
                path.unlink(missing_ok=True)
            if ctx_token is not None:
                reset_request_id(ctx_token)

    def resolve_manual_review(
        self, review_id: UUID, *, resolved_by: str | None = None
    ) -> dict:
        row = self._db.get_manual_review(review_id)
        if not row:
            raise FileNotFoundError("Review item not found")
        return self._db.resolve_manual_review(review_id, resolved_by=resolved_by)

    def _mark_job_failed(self, document_id: UUID, error: str) -> None:
        row = self._db.get_document(document_id)
        if not row:
            return
        raw = self._coerce_mapping(row.get("raw_extraction"))
        started_at = raw.get("started_at") if isinstance(raw.get("started_at"), str) else None
        payload = SupabaseClient.document_payload(
            bankruptcy_id=UUID(str(row["bankruptcy_id"]))
            if row.get("bankruptcy_id")
            else None,
            s3_key=str(row.get("s3_key", "")),
            content_sha256=str(row.get("content_sha256", "")),
            page_count=int(row.get("page_count") or 0),
            filing_type=FilingType(row.get("filing_type", FilingType.UNKNOWN.value)),
            parse_mode=ParseMode(row.get("parse_mode", ParseMode.STRUCTURED.value)),
            ocr_used=bool(row.get("ocr_used")),
            parser_version=str(row.get("parser_version", self._settings.parser_version)),
            raw_extraction=failed_job_raw(error=error, started_at=started_at),
        )
        self._db.upsert_document(payload)

    @staticmethod
    def _processing_response(*, document_id: UUID) -> ParseDocumentResponse:
        return ParseDocumentResponse(
            status="processing",
            document_id=document_id,
            manual_review_required=False,
        )

    def _parse_document_sync(
        self,
        *,
        path: Path,
        key: str,
        content_hash: str,
        bankruptcy_id: UUID | None,
        docket_hint: FilingType | None,
        force: bool,
        document_id: UUID | None,
    ) -> ParseDocumentResponse:
        try:
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

            active_document_id = self._resolve_document_id(
                document_id=document_id, content_hash=content_hash
            )
            bankruptcy = (
                self._db.get_bankruptcy(bankruptcy_id) if bankruptcy_id else None
            )
            case_number = bankruptcy["case_number"] if bankruptcy else "unknown"

            if ocr_used:
                self._s3.put_text(
                    self._s3.ocr_output_key(case_number, str(active_document_id)),
                    text,
                )

            parsed_key = self._s3.parsed_output_key(case_number, str(active_document_id))
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

            raw_extraction = mark_raw_completed(
                {
                    "text_preview": text[:2000],
                    "filing_type": filing_type.value,
                    "ocr_confidence": ocr_confidence,
                    "parsed_s3_key": parsed_key,
                    "validation": validation.model_dump(),
                    "manual_review_required": validation.manual_review_required,
                    "form201": form201.model_dump() if form201 else None,
                    "creditors": [c.model_dump() for c in creditors]
                    if creditors
                    else None,
                }
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
                raw_extraction=raw_extraction,
            )
            doc_payload["id"] = str(active_document_id)
            saved = self._db.upsert_document(doc_payload)
            if saved.get("id"):
                active_document_id = UUID(str(saved["id"]))

            if force:
                self._db.delete_parse_artifacts_for_document(active_document_id)

            if form201 and bankruptcy_id:
                self._db.replace_form201_extraction(
                    SupabaseClient.form201_to_row(
                        active_document_id,
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
                matrix_rows = [
                    {
                        "extraction_id": str(extraction_id),
                        "creditor_name": row.creditor_name,
                        "address": row.address,
                        "claim_amount": row.claim_amount,
                        "entity_type": row.entity_type,
                    }
                    for row in creditors
                ]
                self._db.replace_creditor_matrix_extraction(
                    {
                        "id": str(extraction_id),
                        "document_id": str(active_document_id),
                        "bankruptcy_id": str(bankruptcy_id),
                        "creditor_count": len(creditors),
                        "confidence_score": validation.confidence_score,
                        "manual_review_required": validation.manual_review_required,
                        "parser_version": self._settings.parser_version,
                    },
                    matrix_rows,
                )
                if not validation.manual_review_required:
                    self._db.merge_creditors(
                        bankruptcy_id,
                        creditors,
                        confidence_score=validation.confidence_score,
                    )

            if validation.manual_review_required and not self._db.has_pending_manual_review(
                active_document_id
            ):
                self._db.insert_manual_review(
                    {
                        "bankruptcy_id": str(bankruptcy_id) if bankruptcy_id else None,
                        "document_id": str(active_document_id),
                        "review_reason": ",".join(validation.missing_fields)
                        or "low_confidence",
                        "status": "pending",
                    }
                )

            confidence = validation.confidence_score
            if ocr_used:
                confidence = min(confidence, ocr_confidence)

            if bankruptcy_id:
                self._db.upsert_case_status(
                    bankruptcy_id,
                    has_creditor_matrix=(
                        filing_type == FilingType.CREDITOR_MATRIX and bool(creditors)
                    ),
                    lifecycle_stage="parsed",
                )

            return ParseDocumentResponse(
                status="completed",
                filing_type=filing_type,
                parse_mode=parse_mode,
                ocr_used=ocr_used,
                page_count=page_count,
                confidence=confidence,
                manual_review_required=validation.manual_review_required,
                document_id=active_document_id,
                form201=form201,
                creditors=creditors,
                validation=validation,
            )
        except Exception as exc:
            if document_id is not None:
                self._mark_job_failed(document_id, str(exc))
            raise

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
        document_id = UUID(str(row["id"])) if row.get("id") else None
        job_status = job_status_from_raw(raw)

        if job_status == JOB_STATUS_PROCESSING:
            if document_id is None:
                raise ValueError("Processing document row is missing id")
            return self._processing_response(document_id=document_id)

        if job_status == JOB_STATUS_FAILED:
            error = raw.get("job_error")
            return ParseDocumentResponse(
                status="failed",
                document_id=document_id,
                error=str(error) if error is not None else "parse failed",
                manual_review_required=False,
            )

        validation = self._validation_from_cached_row(row, raw)
        if document_id and self._db.has_pending_manual_review(document_id):
            validation = validation.model_copy(update={"manual_review_required": True})
        return ParseDocumentResponse(
            status="completed",
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
        job_status = job_status_from_raw(raw)
        filing = row.get("filing_type")

        if job_status == JOB_STATUS_PROCESSING:
            return JobStatusResponse(
                document_id=document_id,
                status="processing",
                parser_version=str(row.get("parser_version", "")),
                filing_type=FilingType(filing) if filing else None,
                manual_review_required=False,
                result=raw or None,
            )

        if job_status == JOB_STATUS_FAILED:
            error = raw.get("job_error")
            return JobStatusResponse(
                document_id=document_id,
                status="failed",
                parser_version=str(row.get("parser_version", "")),
                filing_type=FilingType(filing) if filing else None,
                manual_review_required=False,
                result=raw or None,
                error=str(error) if error is not None else "parse failed",
            )

        validation = self._validation_from_cached_row(row, raw)
        if self._db.has_pending_manual_review(document_id):
            validation = validation.model_copy(update={"manual_review_required": True})
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
