"""
API tests for KD-40 creditor deduplication (FR-3.5 / AC-3.5).

Uses real DocumentPipeline + fake S3/Supabase (not mocked parse_document).
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from app.core.config import get_settings
from app.pipeline.job_status import RAW_CREDITORS_MERGED, mark_raw_completed
from fastapi.testclient import TestClient
from tests.helpers.dedup_api_fixtures import (
    DEDUP_MATRIX_DIFF_ADDR_KEY,
    DEDUP_MATRIX_KEY,
    dedup_api_env,
    dedup_bankruptcy_id,
)
from tests.helpers.fake_supabase import FakeSupabaseClient


def _matrix_parse_payload(bankruptcy_id: UUID, *, force: bool) -> dict[str, object]:
    return {
        "bankruptcy_id": str(bankruptcy_id),
        "s3_key": DEDUP_MATRIX_KEY,
        "docket_hint": "CREDITOR_MATRIX",
        "force": force,
    }


def _find_creditor_by_substring(creditors: list[dict], needle: str) -> dict | None:
    for row in creditors:
        if needle in row.get("creditor_name", ""):
            return row
    return None


class TestExtractCreditorMatrixCreditorDedup:
    def test_extract_creditor_matrix_dedupes_fuzzy_duplicates(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        dedup_bankruptcy_id: UUID,
        dedup_api_env: FakeSupabaseClient,
    ) -> None:
        response = client.post(
            "/api/v1/extract/creditor-matrix",
            json={
                "bankruptcy_id": str(dedup_bankruptcy_id),
                "s3_key": DEDUP_MATRIX_KEY,
                "docket_hint": "CREDITOR_MATRIX",
                "force": True,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["filing_type"] == "CREDITOR_MATRIX"
        assert body["creditor_count"] == 2
        creditors = body["creditors"]
        assert len(creditors) == 2
        abc = _find_creditor_by_substring(creditors, "ABC")
        assert abc is not None
        assert abc["claim_amount"] == pytest.approx(150.0)
        assert abc.get("dedup_audit") is not None


class TestParseDocumentCreditorDedup:
    def test_happy_path_dedupes_fuzzy_duplicates(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        dedup_bankruptcy_id: UUID,
        dedup_api_env: FakeSupabaseClient,
    ) -> None:
        response = client.post(
            "/api/v1/parse/document",
            json=_matrix_parse_payload(dedup_bankruptcy_id, force=True),
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "completed"
        assert body["filing_type"] == "CREDITOR_MATRIX"
        creditors = body["creditors"]
        assert creditors is not None
        assert len(creditors) == 2

        abc = _find_creditor_by_substring(creditors, "ABC")
        assert abc is not None
        assert abc["claim_amount"] == pytest.approx(150.0)
        assert abc.get("dedup_audit") is not None
        assert abc.get("dedup_audit", {}).get("duplicate_count") == 2
        assert "ABC Corp" in (abc.get("dedup_audit") or {}).get("merged_names", [])
        assert sorted(abc.get("source_line_numbers") or []) == [1, 2]

        jane = _find_creditor_by_substring(creditors, "Jane")
        assert jane is not None
        assert jane.get("dedup_audit") is None

        raw = FakeSupabaseClient._documents[str(body["document_id"])]["raw_extraction"]
        assert raw.get("dedup_stats", {}).get("original_count") == 3
        assert raw.get("dedup_stats", {}).get("deduped_count") == 2

    def test_cache_hit_returns_deduped_creditors_without_re_merge(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        dedup_bankruptcy_id: UUID,
        dedup_api_env: FakeSupabaseClient,
    ) -> None:
        first = client.post(
            "/api/v1/parse/document",
            json=_matrix_parse_payload(dedup_bankruptcy_id, force=True),
            headers=auth_headers,
        )
        assert first.status_code == 200, first.text
        first_body = first.json()
        assert len(first_body["creditors"]) == 2
        doc = FakeSupabaseClient._documents[str(first_body["document_id"])]
        assert doc["raw_extraction"].get(RAW_CREDITORS_MERGED) is True

        FakeSupabaseClient.merge_creditors_call_count = 0
        second = client.post(
            "/api/v1/parse/document",
            json=_matrix_parse_payload(dedup_bankruptcy_id, force=False),
            headers=auth_headers,
        )
        assert second.status_code == 200, second.text
        creditors = second.json()["creditors"]
        assert len(creditors) == 2
        abc = _find_creditor_by_substring(creditors, "ABC")
        assert abc is not None
        assert abc["claim_amount"] == pytest.approx(150.0)
        assert FakeSupabaseClient.merge_creditors_call_count == 0
        assert doc["raw_extraction"].get("dedup_stats", {}).get("deduped_count") == 2

    def test_cache_hit_backfill_merge_when_creditors_merged_flag_cleared(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        dedup_bankruptcy_id: UUID,
        dedup_api_env: FakeSupabaseClient,
    ) -> None:
        """Simulates legacy row where parse succeeded but merge_creditors never ran."""
        first = client.post(
            "/api/v1/parse/document",
            json=_matrix_parse_payload(dedup_bankruptcy_id, force=True),
            headers=auth_headers,
        )
        assert first.status_code == 200, first.text
        document_id = first.json()["document_id"]
        doc = FakeSupabaseClient._documents[str(document_id)]
        doc["raw_extraction"].pop(RAW_CREDITORS_MERGED, None)

        FakeSupabaseClient.merge_creditors_call_count = 0
        second = client.post(
            "/api/v1/parse/document",
            json=_matrix_parse_payload(dedup_bankruptcy_id, force=False),
            headers=auth_headers,
        )
        assert second.status_code == 200, second.text
        assert FakeSupabaseClient.merge_creditors_call_count == 1
        stored = FakeSupabaseClient._documents[str(document_id)]["raw_extraction"]
        assert stored.get(RAW_CREDITORS_MERGED) is True

    def test_same_name_different_address_keeps_two_creditors(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        dedup_bankruptcy_id: UUID,
        dedup_api_env: FakeSupabaseClient,
    ) -> None:
        response = client.post(
            "/api/v1/parse/document",
            json={
                "bankruptcy_id": str(dedup_bankruptcy_id),
                "s3_key": DEDUP_MATRIX_DIFF_ADDR_KEY,
                "docket_hint": "CREDITOR_MATRIX",
                "force": True,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        creditors = response.json()["creditors"]
        assert creditors is not None
        assert len(creditors) == 2
        acme_rows = [c for c in creditors if "Acme" in c["creditor_name"]]
        assert len(acme_rows) == 2
        addresses = {c.get("address") or "" for c in acme_rows}
        assert any("Main" in a for a in addresses)
        assert any("Oak" in a for a in addresses)
        assert all(c.get("dedup_audit") is None for c in acme_rows)

    def test_creditor_response_contract_no_internal_fields(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        dedup_bankruptcy_id: UUID,
        dedup_api_env: FakeSupabaseClient,
    ) -> None:
        response = client.post(
            "/api/v1/parse/document",
            json=_matrix_parse_payload(dedup_bankruptcy_id, force=True),
            headers=auth_headers,
        )
        assert response.status_code == 200
        creditor = response.json()["creditors"][0]
        assert set(creditor.keys()) >= {
            "creditor_name",
            "address",
            "claim_amount",
            "entity_type",
            "source_line_numbers",
        }
        assert "password" not in creditor
        assert "api_key" not in creditor

    def test_creditor_dedup_disabled_returns_all_extracted_rows(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        dedup_bankruptcy_id: UUID,
        dedup_api_env: FakeSupabaseClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("CREDITOR_DEDUP_ENABLED", "false")
        get_settings.cache_clear()
        monkeypatch.setattr(
            "app.core.runtime_config.apply_runtime_config",
            lambda s: s.model_copy(update={"creditor_dedup_enabled": False}),
        )
        get_settings.cache_clear()
        FakeSupabaseClient._documents.clear()

        response = client.post(
            "/api/v1/parse/document",
            json=_matrix_parse_payload(dedup_bankruptcy_id, force=True),
            headers=auth_headers,
        )
        get_settings.cache_clear()
        assert response.status_code == 200, response.text
        assert len(response.json()["creditors"]) == 3

    def test_missing_auth_returns_401(
        self,
        client: TestClient,
        dedup_bankruptcy_id: UUID,
        dedup_api_env: FakeSupabaseClient,
    ) -> None:
        response = client.post(
            "/api/v1/parse/document",
            json=_matrix_parse_payload(dedup_bankruptcy_id, force=True),
        )
        assert response.status_code in (401, 403)

    def test_invalid_bankruptcy_id_returns_422(
        self, client: TestClient, auth_headers: dict[str, str]
    ) -> None:
        response = client.post(
            "/api/v1/parse/document",
            json={
                "bankruptcy_id": "not-a-uuid",
                "s3_key": DEDUP_MATRIX_KEY,
                "docket_hint": "CREDITOR_MATRIX",
            },
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_get_job_status_returns_deduped_creditors_in_result(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        dedup_bankruptcy_id: UUID,
        dedup_api_env: FakeSupabaseClient,
    ) -> None:
        parse_resp = client.post(
            "/api/v1/parse/document",
            json=_matrix_parse_payload(dedup_bankruptcy_id, force=True),
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
        assert job_body["status"] == "completed"
        assert job_body["filing_type"] == "CREDITOR_MATRIX"
        result = job_body.get("result") or {}
        creditors = result.get("creditors") or []
        assert len(creditors) == 2
        abc = _find_creditor_by_substring(creditors, "ABC")
        assert abc is not None
        assert abc["claim_amount"] == pytest.approx(150.0)

    def test_still_processing_returns_409(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        dedup_bankruptcy_id: UUID,
        dedup_api_env: FakeSupabaseClient,
        patch_pipeline,
    ) -> None:
        from app.core.exceptions import DocumentProcessingError

        def _raise_processing(self, **kwargs: object) -> None:
            raise DocumentProcessingError("Document is still processing")

        patch_pipeline("parse_document", _raise_processing)
        response = client.post(
            "/api/v1/parse/document",
            json=_matrix_parse_payload(dedup_bankruptcy_id, force=True),
            headers=auth_headers,
        )
        assert response.status_code == 409
        assert "still processing" in response.json()["detail"].lower()


class TestApplyReviewCreditorDedup:
    def _seed_matrix_review(
        self, *, bankruptcy_id: UUID, review_id: UUID, document_id: UUID
    ) -> None:
        settings = get_settings()
        raw = mark_raw_completed(
            {
                "filing_type": "CREDITOR_MATRIX",
                "manual_review_required": True,
                "validation": {
                    "confidence_score": 0.7,
                    "manual_review_required": True,
                    "missing_fields": [],
                    "level": "medium",
                },
            }
        )
        FakeSupabaseClient._documents[str(document_id)] = {
            "id": str(document_id),
            "bankruptcy_id": str(bankruptcy_id),
            "s3_key": DEDUP_MATRIX_KEY,
            "filing_type": "CREDITOR_MATRIX",
            "parse_mode": "structured",
            "ocr_used": False,
            "page_count": 1,
            "parser_version": settings.parser_version,
            "content_sha256": "seed-dedup-doc",
            "raw_extraction": raw,
        }
        FakeSupabaseClient._reviews.append(
            {
                "id": str(review_id),
                "bankruptcy_id": str(bankruptcy_id),
                "document_id": str(document_id),
                "review_reason": "low_confidence",
                "status": "pending",
            }
        )

    def test_apply_dedupes_corrected_creditors(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        dedup_bankruptcy_id: UUID,
        dedup_api_env: FakeSupabaseClient,
    ) -> None:
        review_id = uuid4()
        document_id = uuid4()
        self._seed_matrix_review(
            bankruptcy_id=dedup_bankruptcy_id,
            review_id=review_id,
            document_id=document_id,
        )
        FakeSupabaseClient.merge_creditors_call_count = 0

        response = client.post(
            f"/api/v1/review/{review_id}/apply",
            json={
                "resolved_by": "reviewer",
                "creditors": [
                    {
                        "creditor_name": "ABC Corp",
                        "address": "123 Main St",
                        "claim_amount": 100.0,
                        "entity_type": "company",
                    },
                    {
                        "creditor_name": "ABC Corporation",
                        "address": "123 Main St",
                        "claim_amount": 50.0,
                        "entity_type": "company",
                    },
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "resolved"
        assert body["creditor_count"] == 1
        assert FakeSupabaseClient.merge_creditors_call_count == 1

    def test_merge_creditors_receives_dedup_audit_and_source_lines(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        dedup_bankruptcy_id: UUID,
        dedup_api_env: FakeSupabaseClient,
    ) -> None:
        response = client.post(
            "/api/v1/parse/document",
            json=_matrix_parse_payload(dedup_bankruptcy_id, force=True),
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        merged = FakeSupabaseClient.last_merge_creditors
        assert merged is not None
        abc = next((c for c in merged if "ABC" in c.creditor_name), None)
        assert abc is not None
        assert abc.dedup_audit is not None
        assert abc.source_line_numbers

    def test_apply_requires_creditors_or_form201(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        dedup_api_env: FakeSupabaseClient,
    ) -> None:
        response = client.post(
            f"/api/v1/review/{uuid4()}/apply",
            json={"resolved_by": "reviewer"},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_apply_not_found_returns_404(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        dedup_api_env: FakeSupabaseClient,
    ) -> None:
        response = client.post(
            f"/api/v1/review/{uuid4()}/apply",
            json={
                "creditors": [
                    {
                        "creditor_name": "Solo Co",
                        "address": "1 St",
                        "claim_amount": 1.0,
                    }
                ],
            },
            headers=auth_headers,
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Review item not found"
