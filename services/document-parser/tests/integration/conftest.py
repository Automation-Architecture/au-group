"""Fixtures for live integration tests (pytest -m integration)."""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from app.core.config import get_settings
from app.main import app
from fastapi.testclient import TestClient
from tests.helpers.integration_env import integration_env_ready, load_integration_env
from tests.helpers.integration_setup import IntegrationProvisioner, new_run_id
from tests.helpers.pdf_fixtures import build_integration_pdfs

pytestmark = pytest.mark.integration


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: live API tests using .env, S3, and Supabase",
    )


@pytest.fixture(scope="session")
def integration_available() -> str:
    ready, reason = integration_env_ready()
    if not ready:
        pytest.skip(reason)
    get_settings.cache_clear()
    return reason


@pytest.fixture(scope="session")
def live_client(integration_available: str) -> TestClient:
    _ = integration_available
    return TestClient(app)


@pytest.fixture(scope="session")
def live_auth_headers(integration_available: str) -> dict[str, str]:
    _ = integration_available
    settings = get_settings()
    return {"X-API-Key": settings.api_key}


@pytest.fixture(scope="session")
def integration_context(integration_available: str) -> Generator[IntegrationProvisioner, None, None]:
    _ = integration_available
    run_id = new_run_id()
    env = load_integration_env(run_id)
    provisioner = IntegrationProvisioner(env)

    with tempfile.TemporaryDirectory(prefix="doc-parser-it-") as tmp:
        form201_path, matrix_path = build_integration_pdfs(Path(tmp))
        provisioner.ensure_bankruptcy()
        provisioner.upload_pdfs(form201_path, matrix_path)
        yield provisioner
        provisioner.teardown()
