"""API tests for Schedule E/F parse path (AU_GROUP-3.1 + KD-40 dedup)."""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path
from uuid import UUID

import pytest
from app.core.config import get_settings
from app.persistence.s3 import S3Client
from fastapi.testclient import TestClient
from tests.helpers.fake_supabase import FakeSupabaseClient
from tests.helpers.pdf_fixtures import SCHEDULE_EF_DEDUP_TEXT, SCHEDULE_EF_TEXT, write_text_pdf

SCHEDULE_EF_KEY = "raw-documents/smoke-test/schedule_ef.pdf"
SCHEDULE_EF_DEDUP_KEY = "raw-documents/smoke-test/schedule_ef_dedup.pdf"


@pytest.fixture
def schedule_bankruptcy_id() -> UUID:
    return UUID("33333333-3333-4333-8333-333333333333")


@pytest.fixture
def schedule_api_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, schedule_bankruptcy_id: UUID
) -> Generator[FakeSupabaseClient, None, None]:
    root = tmp_path / "schedule-pdfs"
    root.mkdir(parents=True, exist_ok=True)
    pdf_path = root / "schedule_ef.pdf"
    dedup_path = root / "schedule_ef_dedup.pdf"
    write_text_pdf(pdf_path, SCHEDULE_EF_TEXT)
    write_text_pdf(dedup_path, SCHEDULE_EF_DEDUP_TEXT)
    key_to_path = {SCHEDULE_EF_KEY: pdf_path, SCHEDULE_EF_DEDUP_KEY: dedup_path}

    patcher = pytest.MonkeyPatch()
    root_str = str(root.resolve())
    patcher.setenv("ALLOW_LOCAL_FILE_URLS", "true")
    patcher.setenv("LOCAL_FILE_ROOT", root_str)
    patcher.setenv("REQUIRE_BANKRUPTCY_ID", "true")
    patcher.setenv("CREDITOR_DEDUP_ENABLED", "true")
    get_settings.cache_clear()

    FakeSupabaseClient._documents.clear()
    FakeSupabaseClient._reviews.clear()
    fake_db = FakeSupabaseClient()

    def _download_to_temp(self: S3Client, s3_key: str) -> Path:
        source = key_to_path.get(s3_key)
        if source is None or not source.is_file():
            raise FileNotFoundError(f"S3 object not found: {s3_key}")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp_path = Path(tmp.name)
        tmp.close()
        shutil.copy(source, tmp_path)
        return tmp_path

    def _noop_put(self: S3Client, s3_key: str, content: str) -> None:
        return None

    patcher.setattr(S3Client, "download_to_temp", _download_to_temp)
    patcher.setattr(S3Client, "put_text", _noop_put)
    patcher.setattr(S3Client, "put_json", _noop_put)
    patcher.setattr("app.pipeline.router.SupabaseClient", FakeSupabaseClient)

    yield fake_db
    patcher.undo()
    get_settings.cache_clear()


class TestParseDocumentScheduleEf:
    def test_happy_path_extracts_creditors(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        schedule_bankruptcy_id: UUID,
        schedule_api_env: FakeSupabaseClient,
    ) -> None:
        response = client.post(
            "/api/v1/parse/document",
            json={
                "bankruptcy_id": str(schedule_bankruptcy_id),
                "s3_key": SCHEDULE_EF_KEY,
                "docket_hint": "SCHEDULE",
                "force": True,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "completed"
        assert body["filing_type"] == "SCHEDULE"
        creditors = body["creditors"]
        assert creditors is not None
        assert len(creditors) == 2
        assert any("Widget" in c["creditor_name"] for c in creditors)

    def test_schedule_path_dedupes_fuzzy_duplicates(
        self,
        client: TestClient,
        auth_headers: dict[str, str],
        schedule_bankruptcy_id: UUID,
        schedule_api_env: FakeSupabaseClient,
    ) -> None:
        response = client.post(
            "/api/v1/parse/document",
            json={
                "bankruptcy_id": str(schedule_bankruptcy_id),
                "s3_key": SCHEDULE_EF_DEDUP_KEY,
                "docket_hint": "SCHEDULE",
                "force": True,
            },
            headers=auth_headers,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        creditors = body["creditors"]
        assert creditors is not None
        assert len(creditors) == 1
        assert creditors[0]["claim_amount"] == pytest.approx(150.0)
        raw = FakeSupabaseClient._documents[str(body["document_id"])]["raw_extraction"]
        assert raw.get("dedup_stats", {}).get("duplicates_removed") == 1
