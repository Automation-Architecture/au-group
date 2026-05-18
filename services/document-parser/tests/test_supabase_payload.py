from uuid import uuid4

from app.models.schemas import FilingType, ParseMode
from app.persistence.supabase import SupabaseClient


def test_document_payload_omits_null_bankruptcy_id() -> None:
    payload = SupabaseClient.document_payload(
        bankruptcy_id=None,
        s3_key="raw-documents/case/file.pdf",
        content_sha256="abc",
        page_count=1,
        filing_type=FilingType.FORM_201,
        parse_mode=ParseMode.STRUCTURED,
        ocr_used=False,
        parser_version="0.1.0",
        raw_extraction=None,
    )
    assert "bankruptcy_id" not in payload
    assert "raw_extraction" not in payload


def test_document_payload_includes_bankruptcy_id_when_set() -> None:
    bankruptcy_id = uuid4()
    payload = SupabaseClient.document_payload(
        bankruptcy_id=bankruptcy_id,
        s3_key="raw-documents/case/file.pdf",
        content_sha256="abc",
        page_count=1,
        filing_type=FilingType.FORM_201,
        parse_mode=ParseMode.STRUCTURED,
        ocr_used=False,
        parser_version="0.1.0",
        raw_extraction={"ocr_confidence": 0.9},
    )
    assert payload["bankruptcy_id"] == str(bankruptcy_id)
    assert payload["raw_extraction"]["ocr_confidence"] == 0.9
