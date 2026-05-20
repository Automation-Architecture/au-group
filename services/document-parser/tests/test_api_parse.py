"""Functional, validation, contract, and security tests for /api/v1/parse/*."""

import time
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.models.schemas import ParseMode
from tests.conftest import sample_parse_document_response, sample_parse_text_response


class TestParseStructured:
    def test_happy_path_contract(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        patch_pipeline,
    ) -> None:
        mock_response = sample_parse_text_response()
        patch_pipeline("parse_structured", lambda self, **kwargs: mock_response)

        response = client.post(
            "/api/v1/parse/structured",
            json={"s3_key": "raw-documents/24-10001/doc.pdf"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["text"] == mock_response.text
        assert body["page_count"] == mock_response.page_count
        assert body["ocr_used"] is False
        assert body["parse_mode"] == ParseMode.STRUCTURED.value
        assert "password" not in body
        assert "api_key" not in body

    def test_missing_s3_key_and_url_returns_400(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        response = client.post(
            "/api/v1/parse/structured",
            json={},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid request"

    def test_s3_not_found_returns_404(
        self, client: TestClient, auth_headers: dict[str, str], patch_pipeline
    ) -> None:
        def _raise_not_found(self, **kwargs: object) -> None:
            raise FileNotFoundError("S3 object not found: missing.pdf")

        patch_pipeline("parse_structured", _raise_not_found)
        response = client.post(
            "/api/v1/parse/structured",
            json={"s3_key": "raw-documents/24-10001/missing.pdf"},
            headers=auth_headers,
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Not found"

    def test_ignores_mass_assignment_extra_fields(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        patch_pipeline,
    ) -> None:
        patch_pipeline("parse_structured", lambda self, **kwargs: sample_parse_text_response())
        response = client.post(
            "/api/v1/parse/structured",
            json={
                "s3_key": "raw-documents/1/doc.pdf",
                "role": "admin",
                "is_superuser": True,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert "role" not in response.json()
        assert "is_superuser" not in response.json()

    def test_sql_injection_in_s3_key_does_not_crash(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        patch_pipeline,
    ) -> None:
        patch_pipeline("parse_structured", lambda self, **kwargs: sample_parse_text_response())
        response = client.post(
            "/api/v1/parse/structured",
            json={"s3_key": "raw'; DROP TABLE documents;--.pdf"},
            headers=auth_headers,
        )
        assert response.status_code == 422


class TestParseOcr:
    def test_happy_path(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        patch_pipeline,
    ) -> None:
        mock_response = sample_parse_text_response()
        mock_response = mock_response.model_copy(
            update={"ocr_used": True, "parse_mode": ParseMode.OCR, "confidence": 0.88}
        )
        patch_pipeline("parse_ocr", lambda self, **kwargs: mock_response)

        response = client.post(
            "/api/v1/parse/ocr",
            json={"s3_key": "raw-documents/1/scan.pdf"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["ocr_used"] is True
        assert body["parse_mode"] == ParseMode.OCR.value
        assert body["confidence"] == pytest.approx(0.88)

    def test_permission_error_returns_403(
        self, client: TestClient, auth_headers: dict[str, str], patch_pipeline
    ) -> None:
        def _raise_permission(self, **kwargs: object) -> None:
            raise PermissionError("S3 access denied")

        patch_pipeline("parse_ocr", _raise_permission)
        response = client.post(
            "/api/v1/parse/ocr",
            json={"s3_key": "raw-documents/24-10001/forbidden.pdf"},
            headers=auth_headers,
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Forbidden"


class TestParseDocument:
    def test_happy_path_contract(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        bankruptcy_id,
        patch_pipeline,
    ) -> None:
        mock_response = sample_parse_document_response()
        patch_pipeline(
            "parse_document",
            lambda self, **kwargs: (mock_response, False, None, None, None, False),
        )

        response = client.post(
            "/api/v1/parse/document",
            json={
                "bankruptcy_id": str(bankruptcy_id),
                "s3_key": "raw-documents/24-10001/form201.pdf",
                "docket_hint": "FORM_201",
                "force": False,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "completed"
        assert body["filing_type"] == "FORM_201"
        assert body["manual_review_required"] is False
        assert body["form201"]["debtor_name"] == "Acme Corp"
        assert body["validation"]["confidence_score"] == pytest.approx(0.92)
        assert "password" not in body

    def test_missing_bankruptcy_id_returns_400_when_required(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from app.core.config import get_settings

        settings = get_settings()
        monkeypatch.setattr(settings, "require_bankruptcy_id", True)
        get_settings.cache_clear()

        response = client.post(
            "/api/v1/parse/document",
            json={"s3_key": "raw-documents/24-10001/form201.pdf"},
            headers=auth_headers,
        )
        get_settings.cache_clear()
        assert response.status_code == 400
        assert "bankruptcy_id" in response.json()["detail"].lower()

    def test_invalid_bankruptcy_id_returns_422(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        response = client.post(
            "/api/v1/parse/document",
            json={"bankruptcy_id": "not-a-uuid", "s3_key": "x.pdf"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_value_error_returns_400(
        self, client: TestClient, auth_headers: dict[str, str], patch_pipeline
    ) -> None:
        def _raise_value(self, **kwargs: object) -> None:
            raise ValueError("PDF exceeds max pages (500)")

        patch_pipeline("parse_document", _raise_value)
        response = client.post(
            "/api/v1/parse/document",
            json={
                "bankruptcy_id": str(uuid4()),
                "s3_key": "raw-documents/24-10001/huge.pdf",
            },
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid request"

    def test_idempotent_response_shape_when_cached(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        bankruptcy_id,
        patch_pipeline,
    ) -> None:
        """Same mocked pipeline output twice yields identical JSON (contract for n8n)."""
        mock_response = sample_parse_document_response()
        patch_pipeline(
            "parse_document",
            lambda self, **kwargs: (mock_response, False, None, None, None, False),
        )
        payload = {
            "bankruptcy_id": str(bankruptcy_id),
            "s3_key": "raw-documents/1/form201.pdf",
            "force": False,
        }
        first = client.post("/api/v1/parse/document", json=payload, headers=auth_headers)
        second = client.post("/api/v1/parse/document", json=payload, headers=auth_headers)
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json() == second.json()

    def test_async_mode_returns_202_with_document_id(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        document_id,
        patch_pipeline,
    ) -> None:
        from app.models.schemas import ParseDocumentResponse

        processing = ParseDocumentResponse(
            status="processing",
            document_id=document_id,
        )
        patch_pipeline(
            "parse_document",
            lambda self, **kwargs: (
                processing,
                True,
                None,
                "abc123",
                "raw-documents/1/large.pdf",
                True,
            ),
        )

        response = client.post(
            "/api/v1/parse/document",
            json={
                "bankruptcy_id": str(uuid4()),
                "s3_key": "raw-documents/24-10001/large.pdf",
                "async_mode": True,
            },
            headers=auth_headers,
        )
        assert response.status_code == 202
        body = response.json()
        assert body["status"] == "processing"
        assert body["document_id"] == str(document_id)


class TestParsePerformance:
    def test_health_p95_under_200ms(self, client: TestClient) -> None:
        durations_ms: list[float] = []
        for _ in range(20):
            start = time.perf_counter()
            response = client.get("/health")
            elapsed_ms = (time.perf_counter() - start) * 1000
            assert response.status_code == 200
            durations_ms.append(elapsed_ms)
        durations_ms.sort()
        p95_index = int(len(durations_ms) * 0.95) - 1
        p95 = durations_ms[max(p95_index, 0)]
        assert p95 < 200, f"health p95 {p95:.1f}ms exceeded 200ms budget"

    def test_mocked_parse_structured_response_under_200ms(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        patch_pipeline,
    ) -> None:
        patch_pipeline("parse_structured", lambda self, **kwargs: sample_parse_text_response())
        start = time.perf_counter()
        response = client.post(
            "/api/v1/parse/structured",
            json={"s3_key": "raw-documents/1/doc.pdf"},
            headers=auth_headers,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert response.status_code == 200
        assert elapsed_ms < 200
