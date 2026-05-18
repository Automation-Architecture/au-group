"""
Live API tests: real .env, S3 uploads, Supabase bankruptcy, dummy PDFs.

Run:
  cd services/document-parser
  pytest tests/integration/ -v -m integration

Requires services/document-parser/.env with API_KEY, Supabase, and S3 credentials.
Optional: INTEGRATION_BANKRUPTCY_ID to reuse an existing bankruptcies row.
"""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from tests.helpers.integration_setup import IntegrationProvisioner

pytestmark = pytest.mark.integration

BLOCKED_STATUSES = {403, 500, 502, 503}


def _assert_ok(response, *, label: str) -> dict[str, Any]:
    assert response.status_code not in BLOCKED_STATUSES, (
        f"{label}: blocked/error {response.status_code} — {response.text}"
    )
    assert response.status_code < 400, f"{label}: {response.status_code} — {response.text}"
    return response.json()


class TestLiveHealth:
    def test_health_no_auth(self, live_client: TestClient) -> None:
        response = live_client.get("/health")
        body = _assert_ok(response, label="GET /health")
        assert body["status"] == "ok"
        assert "parser_version" in body


class TestLiveParse:
    def test_parse_structured_form201_pdf(
        self,
        live_client: TestClient,
        live_auth_headers: dict[str, str],
        integration_context: IntegrationProvisioner,
    ) -> None:
        response = live_client.post(
            "/api/v1/parse/structured",
            json={"s3_key": integration_context.form201_s3_key},
            headers=live_auth_headers,
        )
        body = _assert_ok(response, label="POST /parse/structured")
        assert body["page_count"] >= 1
        assert "Official Form 201" in body["text"] or "Voluntary Petition" in body["text"]
        assert body["parse_mode"] == "structured"
        assert body["ocr_used"] is False

    def test_parse_ocr_form201_pdf(
        self,
        live_client: TestClient,
        live_auth_headers: dict[str, str],
        integration_context: IntegrationProvisioner,
    ) -> None:
        response = live_client.post(
            "/api/v1/parse/ocr",
            json={
                "s3_key": integration_context.form201_s3_key,
                "bankruptcy_id": str(integration_context.bankruptcy_id),
            },
            headers=live_auth_headers,
        )
        body = _assert_ok(response, label="POST /parse/ocr")
        assert body["page_count"] >= 1
        assert len(body["text"]) > 20
        assert body["ocr_used"] is True

    def test_parse_document_form201(
        self,
        live_client: TestClient,
        live_auth_headers: dict[str, str],
        integration_context: IntegrationProvisioner,
    ) -> None:
        response = live_client.post(
            "/api/v1/parse/document",
            json={
                "bankruptcy_id": str(integration_context.bankruptcy_id),
                "s3_key": integration_context.form201_s3_key,
                "docket_hint": "FORM_201",
                "force": True,
            },
            headers=live_auth_headers,
        )
        body = _assert_ok(response, label="POST /parse/document (form201)")
        assert body["filing_type"] == "FORM_201"
        assert body["document_id"] is not None
        assert body["form201"] is not None
        assert body["form201"].get("debtor_name")
        integration_context.last_form201_document_id = UUID(str(body["document_id"]))

    def test_parse_document_creditor_matrix(
        self,
        live_client: TestClient,
        live_auth_headers: dict[str, str],
        integration_context: IntegrationProvisioner,
    ) -> None:
        response = live_client.post(
            "/api/v1/parse/document",
            json={
                "bankruptcy_id": str(integration_context.bankruptcy_id),
                "s3_key": integration_context.matrix_s3_key,
                "docket_hint": "CREDITOR_MATRIX",
                "force": True,
            },
            headers=live_auth_headers,
        )
        body = _assert_ok(response, label="POST /parse/document (matrix)")
        assert body["filing_type"] == "CREDITOR_MATRIX"
        assert body["document_id"] is not None
        assert body["validation"] is not None
        assert body["confidence"] is not None
        assert body["creditors"] is not None
        assert len(body["creditors"]) >= 1
        assert body["creditors"][0].get("creditor_name")


class TestLiveExtract:
    def test_extract_form201(
        self,
        live_client: TestClient,
        live_auth_headers: dict[str, str],
        integration_context: IntegrationProvisioner,
    ) -> None:
        response = live_client.post(
            "/api/v1/extract/form201",
            json={
                "bankruptcy_id": str(integration_context.bankruptcy_id),
                "s3_key": integration_context.form201_s3_key,
                "docket_hint": "FORM_201",
                "force": True,
            },
            headers=live_auth_headers,
        )
        body = _assert_ok(response, label="POST /extract/form201")
        assert body["filing_type"] == "FORM_201"
        assert body["form201"]["debtor_name"]
        assert body["validation"]["confidence_score"] > 0

    def test_extract_creditor_matrix(
        self,
        live_client: TestClient,
        live_auth_headers: dict[str, str],
        integration_context: IntegrationProvisioner,
    ) -> None:
        response = live_client.post(
            "/api/v1/extract/creditor-matrix",
            json={
                "bankruptcy_id": str(integration_context.bankruptcy_id),
                "s3_key": integration_context.matrix_s3_key,
                "docket_hint": "CREDITOR_MATRIX",
                "force": True,
            },
            headers=live_auth_headers,
        )
        body = _assert_ok(response, label="POST /extract/creditor-matrix")
        assert body["filing_type"] == "CREDITOR_MATRIX"
        assert body["validation"] is not None
        assert body["creditor_count"] >= 1
        assert len(body["creditors"]) >= 1
        assert body["creditors"][0]["creditor_name"]


class TestLiveReview:
    def test_review_queue(
        self,
        live_client: TestClient,
        live_auth_headers: dict[str, str],
    ) -> None:
        response = live_client.get(
            "/api/v1/review-queue",
            params={"limit": 5, "offset": 0},
            headers=live_auth_headers,
        )
        body = _assert_ok(response, label="GET /review-queue")
        assert "items" in body
        assert "total" in body
        assert isinstance(body["items"], list)

    def test_job_status_after_parse(
        self,
        live_client: TestClient,
        live_auth_headers: dict[str, str],
        integration_context: IntegrationProvisioner,
    ) -> None:
        doc_id = getattr(integration_context, "last_form201_document_id", None)
        if not doc_id:
            parse_resp = live_client.post(
                "/api/v1/parse/document",
                json={
                    "bankruptcy_id": str(integration_context.bankruptcy_id),
                    "s3_key": integration_context.form201_s3_key,
                    "docket_hint": "FORM_201",
                    "force": True,
                },
                headers=live_auth_headers,
            )
            parse_body = _assert_ok(parse_resp, label="POST /parse/document (for job poll)")
            doc_id = UUID(parse_body["document_id"])

        response = live_client.get(
            f"/api/v1/jobs/{doc_id}",
            headers=live_auth_headers,
        )
        body = _assert_ok(response, label="GET /jobs/{document_id}")
        assert body["document_id"] == str(doc_id)
        assert body["status"] in ("completed", "pending")
        assert body["parser_version"]


class TestLiveJwtAndPersistence:
    def test_jwt_login_then_review_queue(
        self,
        live_client: TestClient,
        integration_context: IntegrationProvisioner,
    ) -> None:
        settings = integration_context._settings
        if not settings.jwt_secret or not settings.auth_username or not settings.auth_password:
            pytest.skip("JWT_SECRET and AUTH_USERNAME/AUTH_PASSWORD required in .env")

        login = live_client.post(
            "/api/v1/auth/login",
            json={"username": settings.auth_username, "password": settings.auth_password},
        )
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]

        response = live_client.get(
            "/api/v1/review-queue",
            params={"limit": 1},
            headers={"Authorization": f"Bearer {token}"},
        )
        _assert_ok(response, label="GET /review-queue (JWT)")

    def test_document_row_in_supabase_after_parse(
        self,
        live_client: TestClient,
        live_auth_headers: dict[str, str],
        integration_context: IntegrationProvisioner,
    ) -> None:
        response = live_client.post(
            "/api/v1/parse/document",
            json={
                "bankruptcy_id": str(integration_context.bankruptcy_id),
                "s3_key": integration_context.form201_s3_key,
                "docket_hint": "FORM_201",
                "force": True,
            },
            headers=live_auth_headers,
        )
        body = _assert_ok(response, label="POST /parse/document (db check)")
        document_id = UUID(str(body["document_id"]))
        row = integration_context.get_document(document_id)
        assert row is not None
        assert str(row["id"]) == str(document_id)
        assert row.get("filing_type") == "FORM_201"


class TestLiveReadiness:
    def test_health_ready(
        self,
        live_client: TestClient,
    ) -> None:
        response = live_client.get("/health/ready")
        assert response.status_code in (200, 503)
        body = response.json()
        assert "checks" in body
        assert "supabase" in body["checks"]
        assert "s3" in body["checks"]
        if response.status_code == 200:
            assert body["status"] == "ready"


class TestLiveAuthAndPerformance:
    def test_wrong_api_key_blocked(self, live_client: TestClient) -> None:
        response = live_client.post(
            "/api/v1/parse/structured",
            json={"s3_key": "any.pdf"},
            headers={"X-API-Key": "definitely-wrong-key"},
        )
        assert response.status_code == 403

    def test_health_latency(self, live_client: TestClient) -> None:
        durations_ms: list[float] = []
        for _ in range(10):
            start = time.perf_counter()
            response = live_client.get("/health")
            durations_ms.append((time.perf_counter() - start) * 1000)
            assert response.status_code == 200
        durations_ms.sort()
        p95 = durations_ms[int(len(durations_ms) * 0.95) - 1]
        assert p95 < 500, f"health p95 {p95:.0f}ms unexpectedly slow"
