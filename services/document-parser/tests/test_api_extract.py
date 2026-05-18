"""Tests for /api/v1/extract/*."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.conftest import (
    sample_extract_creditor_matrix_response,
    sample_extract_form201_response,
)


class TestExtractForm201:
    def test_happy_path_contract(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        bankruptcy_id,
        patch_pipeline,
    ) -> None:
        mock_response = sample_extract_form201_response()
        patch_pipeline("extract_form201", lambda self, **kwargs: mock_response)

        response = client.post(
            "/api/v1/extract/form201",
            json={
                "bankruptcy_id": str(bankruptcy_id),
                "s3_key": "raw-documents/1/form201.pdf",
                "docket_hint": "FORM_201",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["filing_type"] == "FORM_201"
        assert body["form201"]["debtor_name"] == "Acme Corp"
        assert body["validation"]["confidence_score"] == pytest.approx(0.92)
        assert body["document_id"] is not None
        assert "password" not in body
        assert "supabase_service_role_key" not in body

    def test_missing_bankruptcy_id_returns_422(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        response = client.post(
            "/api/v1/extract/form201",
            json={"s3_key": "raw-documents/1/form201.pdf"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_missing_s3_key_returns_422(
        self, client: TestClient, auth_headers: dict[str, str], bankruptcy_id
    ) -> None:
        response = client.post(
            "/api/v1/extract/form201",
            json={"bankruptcy_id": str(bankruptcy_id)},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_invalid_docket_hint_returns_422(
        self, client: TestClient, auth_headers: dict[str, str], bankruptcy_id
    ) -> None:
        response = client.post(
            "/api/v1/extract/form201",
            json={
                "bankruptcy_id": str(bankruptcy_id),
                "s3_key": "raw-documents/1/form201.pdf",
                "docket_hint": "NOT_A_REAL_TYPE",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_pipeline_value_error_returns_400(
        self, client: TestClient, auth_headers: dict[str, str], bankruptcy_id, patch_pipeline
    ) -> None:
        def _raise(self, **kwargs: object) -> None:
            raise ValueError("parse_document() did not return form201 data")

        patch_pipeline("extract_form201", _raise)
        response = client.post(
            "/api/v1/extract/form201",
            json={
                "bankruptcy_id": str(bankruptcy_id),
                "s3_key": "raw-documents/1/bad.pdf",
            },
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid request"


class TestExtractCreditorMatrix:
    def test_happy_path_contract(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        bankruptcy_id,
        patch_pipeline,
    ) -> None:
        mock_response = sample_extract_creditor_matrix_response()
        patch_pipeline("extract_creditor_matrix", lambda self, **kwargs: mock_response)

        response = client.post(
            "/api/v1/extract/creditor-matrix",
            json={
                "bankruptcy_id": str(bankruptcy_id),
                "s3_key": "raw-documents/1/matrix.pdf",
                "docket_hint": "CREDITOR_MATRIX",
                "force": True,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["filing_type"] == "CREDITOR_MATRIX"
        assert body["creditor_count"] == 1
        assert len(body["creditors"]) == 1
        assert body["creditors"][0]["creditor_name"] == "Example Bank NA"

    def test_s3_not_found_returns_404(
        self, client: TestClient, auth_headers: dict[str, str], bankruptcy_id, patch_pipeline
    ) -> None:
        def _raise(self, **kwargs: object) -> None:
            raise FileNotFoundError("S3 object not found: matrix.pdf")

        patch_pipeline("extract_creditor_matrix", _raise)
        response = client.post(
            "/api/v1/extract/creditor-matrix",
            json={
                "bankruptcy_id": str(bankruptcy_id),
                "s3_key": "raw-documents/1/matrix.pdf",
            },
            headers=auth_headers,
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Not found"

    def test_mass_assignment_ignored(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        bankruptcy_id,
        patch_pipeline,
    ) -> None:
        patch_pipeline(
            "extract_creditor_matrix",
            lambda self, **kwargs: sample_extract_creditor_matrix_response(),
        )
        response = client.post(
            "/api/v1/extract/creditor-matrix",
            json={
                "bankruptcy_id": str(bankruptcy_id),
                "s3_key": "raw-documents/1/matrix.pdf",
                "admin": True,
                "bypass_validation": True,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert "admin" not in body
        assert "bypass_validation" not in body
