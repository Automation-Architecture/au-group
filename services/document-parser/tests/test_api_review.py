"""Tests for /api/v1/review-queue and /api/v1/jobs/{document_id}."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from tests.conftest import sample_job_status_response, sample_review_queue_row


class TestReviewQueue:
    def test_happy_path_pagination_contract(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        patch_pipeline,
    ) -> None:
        row = sample_review_queue_row()
        patch_pipeline("list_review_queue", lambda self, **kwargs: ([row], 1))

        response = client.get(
            "/api/v1/review-queue",
            params={"limit": 10, "offset": 0, "status": "pending"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert body["limit"] == 10
        assert body["offset"] == 0
        assert len(body["items"]) == 1
        item = body["items"][0]
        assert item["review_reason"] == "low_confidence"
        assert item["status"] == "pending"
        assert "password" not in item

    def test_limit_validation_edge_cases(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        for params, expected_status in [
            ({"limit": 0}, 422),
            ({"limit": 201}, 422),
            ({"offset": -1}, 422),
        ]:
            response = client.get(
                "/api/v1/review-queue",
                params=params,
                headers=auth_headers,
            )
            assert response.status_code == expected_status

    def test_invalid_status_filter_returns_400(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
    ) -> None:
        response = client.get(
            "/api/v1/review-queue",
            params={"status": "pending' OR '1'='1"},
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]

    def test_empty_queue(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        patch_pipeline,
    ) -> None:
        patch_pipeline("list_review_queue", lambda self, **kwargs: ([], 0))
        response = client.get("/api/v1/review-queue", headers=auth_headers)
        assert response.status_code == 200
        assert response.json() == {"items": [], "total": 0, "limit": 50, "offset": 0}


class TestJobStatus:
    def test_happy_path_contract(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        document_id,
        patch_pipeline,
    ) -> None:
        status = sample_job_status_response(document_id=document_id)
        patch_pipeline("build_job_status", lambda self, _: status)

        response = client.get(f"/api/v1/jobs/{document_id}", headers=auth_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["document_id"] == str(document_id)
        assert body["status"] == "completed"
        assert body["parser_version"] == "0.1.0"
        assert body["filing_type"] == "FORM_201"
        assert body["manual_review_required"] is False
        assert body["result"]["debtor_name"] == "Acme Corp"

    def test_not_found_returns_404(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        patch_pipeline,
    ) -> None:
        patch_pipeline("build_job_status", lambda self, _: None)
        missing_id = uuid4()
        response = client.get(f"/api/v1/jobs/{missing_id}", headers=auth_headers)
        assert response.status_code == 404
        assert response.json()["detail"] == "Document not found"

    def test_invalid_document_id_returns_422(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        response = client.get("/api/v1/jobs/not-a-uuid", headers=auth_headers)
        assert response.status_code == 422

    def test_manual_review_flag_in_response(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        document_id,
        patch_pipeline,
    ) -> None:
        status = sample_job_status_response(document_id=document_id).model_copy(
            update={"manual_review_required": True, "status": "pending"}
        )
        patch_pipeline("build_job_status", lambda self, _: status)
        response = client.get(f"/api/v1/jobs/{document_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["manual_review_required"] is True

    def test_processing_job_status(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        document_id,
        patch_pipeline,
    ) -> None:
        status = sample_job_status_response(document_id=document_id).model_copy(
            update={"status": "processing", "manual_review_required": False}
        )
        patch_pipeline("build_job_status", lambda self, _: status)
        response = client.get(f"/api/v1/jobs/{document_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "processing"


class TestResolveReview:
    def test_resolve_happy_path(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        patch_pipeline,
    ) -> None:
        review_id = uuid4()
        bankruptcy_id = uuid4()
        document_id = uuid4()

        patch_pipeline(
            "resolve_manual_review",
            lambda self, rid, **kwargs: {
                "review_id": str(review_id),
                "document_id": str(document_id),
                "bankruptcy_id": str(bankruptcy_id),
                "status": "resolved",
                "bankruptcy_manual_review_required": False,
            },
        )

        response = client.post(
            f"/api/v1/review/{review_id}/resolve",
            json={"resolved_by": "keith"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "resolved"
        assert body["bankruptcy_manual_review_required"] is False

    def test_resolve_not_found(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        patch_pipeline,
    ) -> None:
        def _raise_not_found(self, review_id: object, **kwargs: object) -> None:
            raise FileNotFoundError("Review item not found")

        patch_pipeline("resolve_manual_review", _raise_not_found)
        response = client.post(
            f"/api/v1/review/{uuid4()}/resolve",
            headers=auth_headers,
        )
        assert response.status_code == 404
