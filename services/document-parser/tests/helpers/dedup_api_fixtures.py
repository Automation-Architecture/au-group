"""Fixtures for KD-40 API tests (real pipeline, fake S3/Supabase)."""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Generator
from pathlib import Path
from uuid import UUID

import pytest
from app.core.config import get_settings
from app.persistence.s3 import S3Client
from tests.helpers.fake_supabase import FakeSupabaseClient
from tests.helpers.pdf_fixtures import (
    CREDITOR_MATRIX_DEDUP_TEXT,
    CREDITOR_MATRIX_SAME_NAME_DIFF_ADDR_TEXT,
    write_text_pdf,
)

DEDUP_MATRIX_KEY = "raw-documents/smoke-test/creditor_matrix_dedup.pdf"
DEDUP_MATRIX_DIFF_ADDR_KEY = "raw-documents/smoke-test/creditor_matrix_diff_addr.pdf"


@pytest.fixture
def dedup_bankruptcy_id() -> UUID:
    return UUID("22222222-2222-4222-8222-222222222222")


@pytest.fixture
def dedup_api_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, dedup_bankruptcy_id: UUID
) -> Generator[FakeSupabaseClient, None, None]:
    root = tmp_path / "dedup-pdfs"
    root.mkdir(parents=True, exist_ok=True)
    matrix_path = root / "creditor_matrix_dedup.pdf"
    diff_addr_path = root / "creditor_matrix_diff_addr.pdf"
    write_text_pdf(matrix_path, CREDITOR_MATRIX_DEDUP_TEXT)
    write_text_pdf(diff_addr_path, CREDITOR_MATRIX_SAME_NAME_DIFF_ADDR_TEXT)
    key_to_path = {
        DEDUP_MATRIX_KEY: matrix_path,
        DEDUP_MATRIX_DIFF_ADDR_KEY: diff_addr_path,
    }

    patcher = pytest.MonkeyPatch()
    root_str = str(root.resolve())
    patcher.setenv("ALLOW_LOCAL_FILE_URLS", "true")
    patcher.setenv("LOCAL_FILE_ROOT", root_str)
    patcher.setenv("REQUIRE_BANKRUPTCY_ID", "true")
    patcher.setenv("CREDITOR_DEDUP_ENABLED", "true")
    get_settings.cache_clear()

    FakeSupabaseClient._documents.clear()
    FakeSupabaseClient._reviews.clear()
    FakeSupabaseClient.merge_creditors_call_count = 0
    FakeSupabaseClient.last_merge_creditors = None
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
