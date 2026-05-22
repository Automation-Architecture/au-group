"""
CI smoke tests: each API route runs against generated dummy PDFs (no live S3/Supabase).

Uses tests/helpers/pdf_fixtures.py text PDFs and in-memory persistence from fake_supabase.py.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from tests.conftest import TEST_AUTH_PASSWORD, TEST_AUTH_USERNAME
from tests.helpers.fake_supabase import FakeSupabaseClient
from tests.helpers.smoke_fixtures import (
    SMOKE_FORM201_KEY,
    SMOKE_MATRIX_KEY,
    dummy_pdf_paths,
    file_url_for,
    smoke_api_env,
    smoke_bankruptcy_id,
)

pytestmark = [pytest.mark.smoke]


class TestSmokeHealthAndAuth:
    def test_health(self, client: TestClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_auth_login(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": TEST_AUTH_USERNAME, "password": TEST_AUTH_PASSWORD},
        )
        assert response.status_code == 200
        assert response.json()["access_token"]


class TestSmokeParseWithDummyPdfs:
    def test_parse_structured_form201(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        smoke_api_env: object,
    ) -> None:
        response = client.post(
            "/api/v1/parse/structured",
            json={"s3_key": SMOKE_FORM201_KEY},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["page_count"] >= 1
        assert "Official Form 201" in body["text"] or "Voluntary Petition" in body["text"]
        assert body["ocr_used"] is False
        assert body["parse_mode"] == "structured"

    def test_parse_ocr_form201(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        smoke_bankruptcy_id: UUID,
        smoke_api_env: object,
    ) -> None:
        response = client.post(
            "/api/v1/parse/ocr",
            json={
                "s3_key": SMOKE_FORM201_KEY,
                "bankruptcy_id": str(smoke_bankruptcy_id),
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["page_count"] >= 1
        assert len(body["text"]) > 20
        assert body["ocr_used"] is True

    def test_parse_document_form201_file_url(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        dummy_pdf_paths: dict,
        smoke_bankruptcy_id: UUID,
        smoke_api_env: object,
    ) -> None:
        response = client.post(
            "/api/v1/parse/document",
            json={
                "bankruptcy_id": str(smoke_bankruptcy_id),
                "document_url": file_url_for(dummy_pdf_paths["form201"]),
                "docket_hint": "FORM_201",
                "force": True,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "completed"
        assert body["filing_type"] == "FORM_201"
        assert body["document_id"] is not None
        assert body["form201"] is not None
        assert body["form201"].get("debtor_name")

    def test_parse_document_creditor_matrix_s3(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        smoke_bankruptcy_id: UUID,
        smoke_api_env: object,
    ) -> None:
        response = client.post(
            "/api/v1/parse/document",
            json={
                "bankruptcy_id": str(smoke_bankruptcy_id),
                "s3_key": SMOKE_MATRIX_KEY,
                "docket_hint": "CREDITOR_MATRIX",
                "force": True,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "completed"
        assert body["filing_type"] == "CREDITOR_MATRIX"
        assert body["document_id"] is not None
        assert body["creditors"] is not None
        assert len(body["creditors"]) >= 1
        names = [c["creditor_name"] for c in body["creditors"]]
        assert any("Acme" in n for n in names)


class TestSmokeExtractWithDummyPdfs:
    def test_extract_form201(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        smoke_bankruptcy_id: UUID,
        smoke_api_env: object,
    ) -> None:
        response = client.post(
            "/api/v1/extract/form201",
            json={
                "bankruptcy_id": str(smoke_bankruptcy_id),
                "s3_key": SMOKE_FORM201_KEY,
                "docket_hint": "FORM_201",
                "force": True,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["filing_type"] == "FORM_201"
        assert body["form201"]["debtor_name"]
        assert body["validation"]["confidence_score"] > 0

    def test_extract_creditor_matrix(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        smoke_bankruptcy_id: UUID,
        smoke_api_env: object,
    ) -> None:
        response = client.post(
            "/api/v1/extract/creditor-matrix",
            json={
                "bankruptcy_id": str(smoke_bankruptcy_id),
                "s3_key": SMOKE_MATRIX_KEY,
                "docket_hint": "CREDITOR_MATRIX",
                "force": True,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["filing_type"] == "CREDITOR_MATRIX"
        assert body["creditor_count"] >= 1
        assert len(body["creditors"]) >= 1


class TestSmokeReviewAndJobs:
    def test_review_queue_empty(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        smoke_api_env: object,
    ) -> None:
        response = client.get(
            "/api/v1/review-queue",
            params={"limit": 10, "offset": 0},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert "items" in body
        assert "total" in body
        assert isinstance(body["items"], list)

    def test_resolve_review(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        smoke_bankruptcy_id: UUID,
        smoke_api_env: FakeSupabaseClient,
    ) -> None:
        review_id = uuid4()
        document_id = uuid4()
        smoke_api_env.insert_manual_review(
            {
                "id": str(review_id),
                "bankruptcy_id": str(smoke_bankruptcy_id),
                "document_id": str(document_id),
                "review_reason": "low_confidence",
                "status": "pending",
            }
        )

        response = client.post(
            f"/api/v1/review/{review_id}/resolve",
            json={"resolved_by": "smoke-ci"},
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["review_id"] == str(review_id)
        assert body["status"] == "resolved"
        assert body["document_id"] == str(document_id)

        stored = smoke_api_env.get_manual_review(review_id)
        assert stored is not None
        assert stored["status"] == "resolved"
        assert stored["assigned_to"] == "smoke-ci"

    def test_job_status_after_parse(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        smoke_bankruptcy_id: UUID,
        smoke_api_env: object,
    ) -> None:
        parse_resp = client.post(
            "/api/v1/parse/document",
            json={
                "bankruptcy_id": str(smoke_bankruptcy_id),
                "s3_key": SMOKE_FORM201_KEY,
                "docket_hint": "FORM_201",
                "force": True,
            },
            headers=auth_headers,
        )
        assert parse_resp.status_code == 200, parse_resp.text
        document_id = parse_resp.json()["document_id"]

        job_resp = client.get(
            f"/api/v1/jobs/{document_id}",
            headers=auth_headers,
        )
        assert job_resp.status_code == 200, job_resp.text
        job_body = job_resp.json()
        assert job_body["document_id"] == document_id
        assert job_body["status"] in ("completed", "pending", "processing")
