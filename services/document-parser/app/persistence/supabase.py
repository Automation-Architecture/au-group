import logging
import re
from typing import Any
from uuid import UUID

import httpx
from app.core.config import ENV_FILE, get_settings
from app.models.schemas import (
    CreditorRow,
    FilingType,
    Form201Data,
    ParseMode,
)
from app.persistence.review_status import validate_review_queue_status

logger = logging.getLogger(__name__)

_CONTENT_RANGE_TOTAL = re.compile(r"/(\d+)$")


class SupabaseUnavailableError(RuntimeError):
    """Supabase REST/RPC unreachable or returned an error."""


class SupabaseClient:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.supabase_url or not settings.supabase_service_role_key:
            logger.warning("Supabase credentials not configured; persistence disabled")
            self._enabled = False
            self._base = ""
            self._headers: dict[str, str] = {}
            return
        self._enabled = True
        self._base = settings.supabase_url.rstrip("/") + "/rest/v1"
        self._headers = {
            "apikey": settings.supabase_service_role_key,
            "Authorization": f"Bearer {settings.supabase_service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: Any = None,
        prefer: str | None = None,
    ) -> Any:
        if not self._enabled:
            return None
        headers = dict(self._headers)
        if prefer:
            headers["Prefer"] = prefer
        url = f"{self._base}/{path.lstrip('/')}"
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json,
                )
        except httpx.ConnectError as exc:
            raise SupabaseUnavailableError(
                "Cannot reach Supabase. Check SUPABASE_URL in "
                f"{ENV_FILE} (or service env) and restart the server after changes."
            ) from exc
        except httpx.HTTPError as exc:
            raise SupabaseUnavailableError(f"Supabase request failed: {exc}") from exc
        if response.status_code >= 400:
            raise SupabaseUnavailableError(
                f"Supabase {method} {path} failed: {response.status_code} {response.text}"
            )
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    def _count_rows(self, path: str, *, filter_params: dict[str, str] | None = None) -> int:
        if not self._enabled:
            return 0
        params: dict[str, str] = {"select": "id", "limit": "1"}
        if filter_params:
            params.update(filter_params)
        headers = dict(self._headers)
        headers["Prefer"] = "count=exact"
        url = f"{self._base}/{path.lstrip('/')}"
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.get(url, headers=headers, params=params)
        except httpx.ConnectError as exc:
            raise SupabaseUnavailableError(
                "Cannot reach Supabase. Check SUPABASE_URL in "
                f"{ENV_FILE} (or service env) and restart the server after changes."
            ) from exc
        except httpx.HTTPError as exc:
            raise SupabaseUnavailableError(f"Supabase request failed: {exc}") from exc
        if response.status_code >= 400:
            raise SupabaseUnavailableError(
                f"Supabase GET {path} count failed: {response.status_code} {response.text}"
            )
        content_range = response.headers.get("content-range", "")
        match = _CONTENT_RANGE_TOTAL.search(content_range)
        if match:
            return int(match.group(1))
        body = response.json() if response.content else []
        return len(body) if isinstance(body, list) else 0

    def get_document(self, document_id: UUID) -> dict[str, Any] | None:
        rows = self._request(
            "GET",
            "documents",
            params={
                "id": f"eq.{document_id}",
                "select": "*",
                "limit": "1",
            },
        )
        if not rows:
            return None
        return rows[0]

    def get_bankruptcy(self, bankruptcy_id: UUID) -> dict[str, Any] | None:
        rows = self._request(
            "GET",
            "bankruptcies",
            params={
                "id": f"eq.{bankruptcy_id}",
                "select": "id,case_number,debtor_name,state,court_district",
                "limit": "1",
            },
        )
        if not rows:
            return None
        return rows[0]

    def find_document_by_hash(
        self, content_sha256: str, parser_version: str
    ) -> dict[str, Any] | None:
        rows = self._request(
            "GET",
            "documents",
            params={
                "content_sha256": f"eq.{content_sha256}",
                "parser_version": f"eq.{parser_version}",
                "select": "*",
                "limit": "1",
            },
        )
        if not rows:
            return None
        return rows[0]

    def upsert_document(self, payload: dict[str, Any]) -> dict[str, Any]:
        explicit_id = payload.get("id")
        upsert_body = {
            k: v
            for k, v in payload.items()
            if v is not None and (k != "id" or explicit_id is not None)
        }
        content_sha256 = upsert_body.get("content_sha256")
        parser_version = upsert_body.get("parser_version")

        existing_document: dict[str, Any] | None = None
        if content_sha256 and parser_version:
            existing_document = self.find_document_by_hash(content_sha256, parser_version)

        if existing_document:
            existing_bankruptcy_id = existing_document.get("bankruptcy_id")
            incoming_bankruptcy_id = upsert_body.get("bankruptcy_id")

            if (
                existing_bankruptcy_id is not None
                and incoming_bankruptcy_id is not None
                and existing_bankruptcy_id != incoming_bankruptcy_id
            ):
                logger.warning(
                    "Refusing to merge document for content_sha256=%s parser_version=%s "
                    "because the existing document is already associated with a different "
                    "bankruptcy_id",
                    content_sha256,
                    parser_version,
                )
                return existing_document

            if existing_bankruptcy_id is not None:
                upsert_body["bankruptcy_id"] = existing_bankruptcy_id

            # Never PATCH primary key when merging an existing row by hash/version.
            upsert_body.pop("id", None)

            rows = self._request(
                "PATCH",
                "documents",
                params={
                    "id": f"eq.{existing_document['id']}",
                    "select": "*",
                },
                json=upsert_body,
                prefer="return=representation",
            )
            if isinstance(rows, list) and rows:
                return rows[0]
            return existing_document

        rows = self._request(
            "POST",
            "documents",
            json=upsert_body,
            prefer="return=representation",
        )
        if isinstance(rows, list) and rows:
            return rows[0]
        return payload

    def has_pending_manual_review(self, document_id: UUID) -> bool:
        rows = self._request(
            "GET",
            "manual_review_queue",
            params={
                "document_id": f"eq.{document_id}",
                "status": "in.(pending,in_review)",
                "select": "id",
                "limit": "1",
            },
        )
        return bool(rows)

    def _delete_creditor_matrix_for_document(self, document_id: UUID) -> None:
        doc_filter = f"eq.{document_id}"
        extractions = self._request(
            "GET",
            "creditor_matrix_extractions",
            params={"document_id": doc_filter, "select": "id"},
        )
        if isinstance(extractions, list):
            for row in extractions:
                extraction_id = row.get("id")
                if extraction_id:
                    self._request(
                        "DELETE",
                        "creditor_matrix_rows",
                        params={"extraction_id": f"eq.{extraction_id}"},
                    )
        self._request(
            "DELETE",
            "creditor_matrix_extractions",
            params={"document_id": doc_filter},
        )

    def delete_parse_artifacts_for_document(self, document_id: UUID) -> None:
        doc_filter = f"eq.{document_id}"
        self._delete_creditor_matrix_for_document(document_id)
        self._request(
            "DELETE",
            "form201_extractions",
            params={"document_id": doc_filter},
        )

    def insert_form201_extraction(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self._request("POST", "form201_extractions", json=payload)
        if isinstance(rows, list) and rows:
            return rows[0]
        return payload

    def replace_form201_extraction(self, payload: dict[str, Any]) -> dict[str, Any]:
        document_id = payload.get("document_id")
        if document_id:
            self._request(
                "DELETE",
                "form201_extractions",
                params={"document_id": f"eq.{document_id}"},
            )
        return self.insert_form201_extraction(payload)

    def insert_creditor_matrix_extraction(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self._request("POST", "creditor_matrix_extractions", json=payload)
        if isinstance(rows, list) and rows:
            return rows[0]
        return payload

    def insert_creditor_matrix_rows(self, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        self._request("POST", "creditor_matrix_rows", json=rows)

    def replace_creditor_matrix_extraction(
        self, extraction_payload: dict[str, Any], row_payloads: list[dict[str, Any]]
    ) -> dict[str, Any]:
        document_id = extraction_payload.get("document_id")
        if document_id:
            self._delete_creditor_matrix_for_document(UUID(str(document_id)))
        saved = self.insert_creditor_matrix_extraction(extraction_payload)
        if row_payloads:
            self.insert_creditor_matrix_rows(row_payloads)
        return saved

    def insert_manual_review(self, payload: dict[str, Any]) -> dict[str, Any]:
        rows = self._request("POST", "manual_review_queue", json=payload)
        if isinstance(rows, list) and rows:
            return rows[0]
        return payload

    def get_manual_review(self, review_id: UUID) -> dict[str, Any] | None:
        rows = self._request(
            "GET",
            "manual_review_queue",
            params={
                "id": f"eq.{review_id}",
                "select": "*",
                "limit": "1",
            },
        )
        if not rows:
            return None
        return rows[0]

    def resolve_manual_review(
        self, review_id: UUID, *, resolved_by: str | None = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"p_review_id": str(review_id)}
        if resolved_by:
            payload["p_resolved_by"] = resolved_by
        result = self._rpc("au_group_resolve_manual_review", payload)
        if not isinstance(result, dict):
            raise RuntimeError("resolve_manual_review returned unexpected payload")
        return result

    def list_manual_review(
        self, *, limit: int = 50, offset: int = 0, status: str | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        status = validate_review_queue_status(status)
        params: dict[str, str] = {
            "select": "*",
            "order": "created_at.desc",
            "limit": str(limit),
            "offset": str(offset),
        }
        filter_params: dict[str, str] = {}
        if status:
            status_filter = f"eq.{status}"
            params["status"] = status_filter
            filter_params["status"] = status_filter
        rows = self._request("GET", "manual_review_queue", params=params) or []
        total = self._count_rows("manual_review_queue", filter_params=filter_params or None)
        return rows, total

    def upsert_bankruptcy_from_form201(
        self,
        bankruptcy_id: UUID,
        form201: Form201Data,
        confidence_score: float,
        manual_review_required: bool,
    ) -> UUID:
        assets = form201.estimated_assets
        liabilities = form201.estimated_liabilities
        creditors = form201.estimated_creditor_count

        payload = {
            "p_bankruptcy_id": str(bankruptcy_id),
            "p_debtor_name": form201.debtor_name,
            "p_city": form201.city,
            "p_state": form201.state,
            "p_court_district": form201.court_district,
            "p_industry_code": form201.industry_code,
            "p_estimated_assets": assets.model_dump() if assets else None,
            "p_estimated_liabilities": liabilities.model_dump() if liabilities else None,
            "p_estimated_creditor_count": creditors.model_dump() if creditors else None,
            "p_confidence_score": confidence_score,
            "p_manual_review_required": manual_review_required,
        }
        result = self._rpc("au_group_upsert_bankruptcy_from_form201", payload)
        if result:
            return UUID(str(result))
        return bankruptcy_id

    def merge_creditors(
        self,
        bankruptcy_id: UUID,
        creditors: list[CreditorRow],
        *,
        confidence_score: float | None = None,
    ) -> int:
        if not creditors:
            return 0
        payload: dict[str, Any] = {
            "p_bankruptcy_id": str(bankruptcy_id),
            "p_creditors": [c.model_dump() for c in creditors],
        }
        if confidence_score is not None:
            payload["p_confidence_score"] = confidence_score
        result = self._rpc("au_group_merge_creditor_matrix", payload)
        return int(result) if result is not None else len(creditors)

    def upsert_case_status(
        self,
        bankruptcy_id: UUID,
        *,
        has_creditor_matrix: bool | None = None,
        has_schedule_f: bool | None = None,
        enrichment_completed: bool | None = None,
        outreach_ready: bool | None = None,
        lifecycle_stage: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {"p_bankruptcy_id": str(bankruptcy_id)}
        if has_creditor_matrix is not None:
            payload["p_has_creditor_matrix"] = has_creditor_matrix
        if has_schedule_f is not None:
            payload["p_has_schedule_f"] = has_schedule_f
        if enrichment_completed is not None:
            payload["p_enrichment_completed"] = enrichment_completed
        if outreach_ready is not None:
            payload["p_outreach_ready"] = outreach_ready
        if lifecycle_stage is not None:
            payload["p_lifecycle_stage"] = lifecycle_stage
        self._rpc("au_group_upsert_case_status", payload)

    def link_document_bankruptcy(self, document_id: UUID, bankruptcy_id: UUID) -> dict[str, Any]:
        result = self._rpc(
            "au_group_link_document_bankruptcy",
            {
                "p_document_id": str(document_id),
                "p_bankruptcy_id": str(bankruptcy_id),
            },
        )
        return result if isinstance(result, dict) else {}

    def _rpc(self, name: str, payload: dict[str, Any]) -> Any:
        if not self._enabled:
            return None
        url = get_settings().supabase_url.rstrip("/") + f"/rest/v1/rpc/{name}"
        with httpx.Client(timeout=60.0) as client:
            try:
                response = client.post(url, headers=self._headers, json=payload)
            except httpx.ConnectError as exc:
                raise SupabaseUnavailableError(f"RPC {name} connection failed") from exc
            except httpx.HTTPError as exc:
                raise SupabaseUnavailableError(f"RPC {name} request failed") from exc
            if response.status_code >= 400:
                raise SupabaseUnavailableError(
                    f"RPC {name} failed: {response.status_code} {response.text}"
                )
            if not response.content:
                return None
            return response.json()

    @staticmethod
    def form201_to_row(
        document_id: UUID,
        bankruptcy_id: UUID | None,
        form201: Form201Data,
        confidence_score: float,
        manual_review_required: bool,
        raw: dict[str, Any],
        parser_version: str,
    ) -> dict[str, Any]:
        return {
            "document_id": str(document_id),
            "bankruptcy_id": str(bankruptcy_id) if bankruptcy_id else None,
            "debtor_name": form201.debtor_name,
            "city": form201.city,
            "state": form201.state,
            "court_district": form201.court_district,
            "industry_code": form201.industry_code,
            "estimated_assets": form201.estimated_assets.model_dump()
            if form201.estimated_assets
            else None,
            "estimated_liabilities": form201.estimated_liabilities.model_dump()
            if form201.estimated_liabilities
            else None,
            "estimated_creditor_count": form201.estimated_creditor_count.model_dump()
            if form201.estimated_creditor_count
            else None,
            "confidence_score": confidence_score,
            "manual_review_required": manual_review_required,
            "raw_extraction": raw,
            "parser_version": parser_version,
        }

    @staticmethod
    def document_payload(
        *,
        bankruptcy_id: UUID | None,
        s3_key: str,
        content_sha256: str,
        page_count: int,
        filing_type: FilingType,
        parse_mode: ParseMode,
        ocr_used: bool,
        parser_version: str,
        raw_extraction: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "s3_key": s3_key,
            "content_sha256": content_sha256,
            "page_count": page_count,
            "filing_type": filing_type.value,
            "parse_mode": parse_mode.value,
            "ocr_used": ocr_used,
            "parser_version": parser_version,
        }
        if bankruptcy_id is not None:
            payload["bankruptcy_id"] = str(bankruptcy_id)
        if raw_extraction is not None:
            payload["raw_extraction"] = raw_extraction
        return payload
