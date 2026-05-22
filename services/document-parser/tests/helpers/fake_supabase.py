"""In-memory Supabase stand-in for CI smoke tests (no network)."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from app.models.schemas import CreditorRow, Form201Data
from app.persistence.review_status import validate_review_queue_status
from app.persistence.supabase import SupabaseClient


class FakeSupabaseClient(SupabaseClient):
    """Minimal persistence fake: enough for parse/extract/review/job routes."""

    _documents: dict[str, dict[str, Any]] = {}
    _reviews: list[dict[str, Any]] = []

    def __init__(self) -> None:
        self._enabled = True

    def get_bankruptcy(self, bankruptcy_id: UUID) -> dict[str, Any] | None:
        return {
            "id": str(bankruptcy_id),
            "case_number": "SMOKE-001",
            "debtor_name": "Smoke Test Debtor",
            "state": "NY",
            "court_district": "Southern District of New York",
        }

    def get_document(self, document_id: UUID) -> dict[str, Any] | None:
        return self._documents.get(str(document_id))

    def find_document_by_hash(
        self, content_sha256: str, parser_version: str
    ) -> dict[str, Any] | None:
        for row in self._documents.values():
            if (
                row.get("content_sha256") == content_sha256
                and row.get("parser_version") == parser_version
            ):
                return row
        return None

    def upsert_document(self, payload: dict[str, Any]) -> dict[str, Any]:
        doc_id = str(payload.get("id") or uuid4())
        row = {**payload, "id": doc_id}
        self._documents[doc_id] = row
        return row

    def has_pending_manual_review(self, document_id: UUID) -> bool:
        doc = str(document_id)
        return any(
            r.get("document_id") == doc and r.get("status") in ("pending", "in_review")
            for r in self._reviews
        )

    def delete_parse_artifacts_for_document(self, document_id: UUID) -> None:
        return None

    def replace_form201_extraction(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload

    def replace_creditor_matrix_extraction(
        self, extraction_payload: dict[str, Any], row_payloads: list[dict[str, Any]]
    ) -> dict[str, Any]:
        return extraction_payload

    def insert_manual_review(self, payload: dict[str, Any]) -> dict[str, Any]:
        row = {**payload, "id": str(payload.get("id") or uuid4())}
        self._reviews.append(row)
        return row

    def list_manual_review(
        self, *, limit: int = 50, offset: int = 0, status: str | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        status = validate_review_queue_status(status)
        rows = self._reviews
        if status:
            rows = [r for r in rows if r.get("status") == status]
        total = len(rows)
        return rows[offset : offset + limit], total

    def get_manual_review(self, review_id: UUID) -> dict[str, Any] | None:
        rid = str(review_id)
        for row in self._reviews:
            if row.get("id") == rid:
                return row
        return None

    def resolve_manual_review(
        self, review_id: UUID, *, resolved_by: str | None = None
    ) -> dict[str, Any]:
        rid = str(review_id)
        for index, row in enumerate(self._reviews):
            if row.get("id") != rid:
                continue
            if row.get("status") not in ("pending", "in_review", "resolved"):
                raise FileNotFoundError("Review item not found")
            if row.get("status") in ("pending", "in_review"):
                assigned_to = resolved_by or row.get("assigned_to")
                updated_row = {
                    **row,
                    "status": "resolved",
                    "assigned_to": assigned_to,
                }
                self._reviews[index] = updated_row
            else:
                updated_row = row
            return {
                "review_id": updated_row["id"],
                "document_id": updated_row.get("document_id"),
                "bankruptcy_id": updated_row.get("bankruptcy_id"),
                "status": updated_row["status"],
                "bankruptcy_manual_review_required": False,
            }
        raise FileNotFoundError("Review item not found")

    def upsert_bankruptcy_from_form201(
        self,
        bankruptcy_id: UUID,
        form201: Form201Data,
        confidence_score: float,
        manual_review_required: bool,
    ) -> UUID:
        return bankruptcy_id

    def merge_creditors(
        self,
        bankruptcy_id: UUID,
        creditors: list[CreditorRow],
        *,
        confidence_score: float | None = None,
    ) -> int:
        return len(creditors)

    def upsert_case_status(self, bankruptcy_id: UUID, **kwargs: Any) -> None:
        return None

    def link_document_bankruptcy(self, document_id: UUID, bankruptcy_id: UUID) -> dict[str, Any]:
        return {"document_id": str(document_id), "bankruptcy_id": str(bankruptcy_id)}
