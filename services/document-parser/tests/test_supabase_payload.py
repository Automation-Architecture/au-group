from uuid import uuid4

from app.models.schemas import FilingType, ParseMode
from app.persistence.supabase import SupabaseClient


def _enabled_client() -> SupabaseClient:
    client = SupabaseClient.__new__(SupabaseClient)
    client._enabled = True
    client._base = "http://example/rest/v1"
    client._headers = {}
    return client


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


def test_upsert_document_omits_id_when_updating_existing_by_hash() -> None:
    client = _enabled_client()
    existing_id = str(uuid4())
    incoming_id = str(uuid4())
    existing = {
        "id": existing_id,
        "content_sha256": "abc",
        "parser_version": "0.1.0",
        "bankruptcy_id": None,
    }
    patch_bodies: list[dict] = []

    def fake_find(content_sha256: str, parser_version: str) -> dict:
        assert content_sha256 == "abc"
        assert parser_version == "0.1.0"
        return existing

    def fake_request(
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict | None = None,
        prefer: str | None = None,
    ) -> list[dict]:
        assert method == "PATCH"
        assert path == "documents"
        assert json is not None
        patch_bodies.append(json)
        return [existing]

    client.find_document_by_hash = fake_find  # type: ignore[method-assign]
    client._request = fake_request  # type: ignore[method-assign]

    result = client.upsert_document(
        {
            "id": incoming_id,
            "content_sha256": "abc",
            "parser_version": "0.1.0",
            "s3_key": "raw-documents/case/file.pdf",
        }
    )

    assert result["id"] == existing_id
    assert "id" not in patch_bodies[0]


def test_has_pending_manual_review_includes_in_review() -> None:
    client = _enabled_client()
    document_id = uuid4()
    captured_params: dict[str, str] = {}

    def fake_request(
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict | None = None,
        prefer: str | None = None,
    ) -> list[dict]:
        assert method == "GET"
        assert path == "manual_review_queue"
        captured_params.update(params or {})
        return [{"id": str(uuid4())}]

    client._request = fake_request  # type: ignore[method-assign]

    assert client.has_pending_manual_review(document_id) is True
    assert captured_params["status"] == "in.(pending,in_review)"
    assert captured_params["document_id"] == f"eq.{document_id}"
