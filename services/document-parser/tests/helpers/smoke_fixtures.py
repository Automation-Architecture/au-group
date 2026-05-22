"""Shared fixtures for dummy-PDF API smoke tests (CI-safe, no live S3/Supabase)."""

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
from tests.helpers.pdf_fixtures import build_integration_pdfs

SMOKE_FORM201_KEY = "raw-documents/smoke-test/form201.pdf"
SMOKE_MATRIX_KEY = "raw-documents/smoke-test/creditor_matrix.pdf"


@pytest.fixture(scope="module")
def dummy_pdf_paths(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("dummy-pdfs")
    form201_path, matrix_path = build_integration_pdfs(root)
    return {
        "root": root,
        "form201": form201_path,
        "matrix": matrix_path,
    }


@pytest.fixture(scope="module")
def smoke_bankruptcy_id() -> UUID:
    return UUID("11111111-1111-4111-8111-111111111111")


@pytest.fixture(scope="module")
def smoke_api_env(dummy_pdf_paths: dict[str, Path]) -> Generator[FakeSupabaseClient, None, None]:
    """Patch settings, S3, and Supabase for one module of real PDF smoke tests."""
    patcher = pytest.MonkeyPatch()
    root = dummy_pdf_paths["root"]
    key_to_path = {
        SMOKE_FORM201_KEY: dummy_pdf_paths["form201"],
        SMOKE_MATRIX_KEY: dummy_pdf_paths["matrix"],
    }

    root_str = str(root.resolve())
    patcher.setenv("ALLOW_LOCAL_FILE_URLS", "true")
    patcher.setenv("LOCAL_FILE_ROOT", root_str)
    patcher.setenv("REQUIRE_BANKRUPTCY_ID", "true")
    get_settings.cache_clear()

    FakeSupabaseClient._documents.clear()
    FakeSupabaseClient._reviews.clear()
    FakeSupabaseClient.merge_creditors_call_count = 0
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


def file_url_for(path: Path) -> str:
    return f"file://{path.resolve()}"
