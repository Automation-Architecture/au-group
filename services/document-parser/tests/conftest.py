import os
from collections.abc import Callable
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

_SERVICE_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv_file() -> None:
    """Load services/document-parser/.env into os.environ (setdefault — no override)."""
    env_path = _SERVICE_ROOT / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_dotenv_file()
# Test credentials must win over services/document-parser/.env (setdefault would not override).
os.environ["AUTH_USERNAME"] = "test-user"
os.environ["AUTH_PASSWORD"] = "test-password"
# Fallback when .env is missing (unit tests).
os.environ.setdefault("API_KEY", "test-api-key-for-pytest-suite-only-do-not-use-in-prod")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("EXPOSE_OPENAPI", "false")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-at-least-32-characters-long")

from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()
from app.main import app  # noqa: E402
from app.models.schemas import (  # noqa: E402
    CreditorRow,
    ExtractCreditorMatrixResponse,
    ExtractForm201Response,
    FilingType,
    Form201Data,
    JobStatusResponse,
    ParseDocumentResponse,
    ParseMode,
    ParseTextResponse,
    ValidationResult,
)


@pytest.fixture
def api_key() -> str:
    return get_settings().api_key


@pytest.fixture
def auth_headers(api_key: str) -> dict[str, str]:
    return {"X-API-Key": api_key}


@pytest.fixture
def bearer_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "test-user", "password": "test-password"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def bankruptcy_id() -> UUID:
    return uuid4()


@pytest.fixture
def document_id() -> UUID:
    return uuid4()


def sample_parse_text_response(*, document_id: UUID | None = None) -> ParseTextResponse:
    return ParseTextResponse(
        text="Official Form 201 voluntary petition",
        page_count=2,
        ocr_used=False,
        confidence=1.0,
        parse_mode=ParseMode.STRUCTURED,
        document_id=document_id or uuid4(),
    )


def sample_parse_document_response(*, document_id: UUID | None = None) -> ParseDocumentResponse:
    doc_id = document_id or uuid4()
    validation = ValidationResult(
        confidence_score=0.92,
        manual_review_required=False,
        missing_fields=[],
        level="high",
    )
    return ParseDocumentResponse(
        status="completed",
        filing_type=FilingType.FORM_201,
        parse_mode=ParseMode.STRUCTURED,
        ocr_used=False,
        page_count=3,
        confidence=0.92,
        manual_review_required=False,
        document_id=doc_id,
        form201=Form201Data(debtor_name="Acme Corp", state="TX"),
        creditors=None,
        validation=validation,
    )


def sample_extract_form201_response(*, document_id: UUID | None = None) -> ExtractForm201Response:
    doc_id = document_id or uuid4()
    return ExtractForm201Response(
        filing_type=FilingType.FORM_201,
        form201=Form201Data(debtor_name="Acme Corp", state="TX"),
        validation=ValidationResult(
            confidence_score=0.92,
            manual_review_required=False,
        ),
        document_id=doc_id,
    )


def sample_extract_creditor_matrix_response(
    *, document_id: UUID | None = None
) -> ExtractCreditorMatrixResponse:
    doc_id = document_id or uuid4()
    creditors = [
        CreditorRow(
            creditor_name="Example Bank NA",
            address="1 Main St",
            claim_amount=1000.0,
            entity_type="company",
        )
    ]
    return ExtractCreditorMatrixResponse(
        filing_type=FilingType.CREDITOR_MATRIX,
        creditors=creditors,
        validation=ValidationResult(
            confidence_score=0.9,
            manual_review_required=False,
        ),
        document_id=doc_id,
        creditor_count=len(creditors),
    )


def sample_job_status_response(*, document_id: UUID) -> JobStatusResponse:
    return JobStatusResponse(
        document_id=document_id,
        status="completed",
        parser_version="0.1.0",
        filing_type=FilingType.FORM_201,
        manual_review_required=False,
        result={"debtor_name": "Acme Corp"},
    )


def sample_review_queue_row(
    *,
    row_id: UUID | None = None,
    bankruptcy_id: UUID | None = None,
    document_id: UUID | None = None,
) -> dict:
    return {
        "id": str(row_id or uuid4()),
        "bankruptcy_id": str(bankruptcy_id or uuid4()),
        "document_id": str(document_id or uuid4()),
        "review_reason": "low_confidence",
        "status": "pending",
        "assigned_to": None,
        "created_at": "2026-05-18T12:00:00+00:00",
    }


@pytest.fixture
def patch_pipeline(monkeypatch: pytest.MonkeyPatch) -> Callable[[str, object], None]:
    """Patch DocumentPipeline methods on all v1 routers that instantiate it."""

    def _patch(method_name: str, replacement: object) -> None:
        from app.api.v1 import extract, parse, review

        for module in (parse, extract, review):
            monkeypatch.setattr(module.DocumentPipeline, method_name, replacement)

    return _patch
