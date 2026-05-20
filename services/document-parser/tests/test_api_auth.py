"""API key and JWT authentication across protected routes."""

from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from tests.conftest import sample_job_status_response, sample_review_queue_row


def _protected_routes(bankruptcy_id: str, document_id: str) -> list[tuple[str, str, dict | None]]:
    return [
        ("POST", "/api/v1/parse/ocr", {"s3_key": "raw-documents/1/test.pdf"}),
        ("POST", "/api/v1/parse/structured", {"s3_key": "raw-documents/1/test.pdf"}),
        (
            "POST",
            "/api/v1/parse/document",
            {
                "bankruptcy_id": bankruptcy_id,
                "s3_key": "raw-documents/1/form201.pdf",
            },
        ),
        (
            "POST",
            "/api/v1/extract/form201",
            {
                "bankruptcy_id": bankruptcy_id,
                "s3_key": "raw-documents/1/form201.pdf",
            },
        ),
        (
            "POST",
            "/api/v1/extract/creditor-matrix",
            {
                "bankruptcy_id": bankruptcy_id,
                "s3_key": "raw-documents/1/matrix.pdf",
            },
        ),
        ("GET", "/api/v1/review-queue", None),
        ("GET", f"/api/v1/jobs/{document_id}", None),
    ]


@pytest.mark.parametrize("header_value", [None, "", "wrong-key"])
def test_protected_routes_reject_missing_or_invalid_api_key(
    client: TestClient,
    header_value: str | None,
) -> None:
    bankruptcy_id = str(uuid4())
    document_id = str(uuid4())
    headers = {"X-API-Key": header_value} if header_value is not None else {}

    for method, path, body in _protected_routes(bankruptcy_id, document_id):
        if method == "POST":
            response = client.post(path, json=body, headers=headers)
        else:
            response = client.get(path, headers=headers)
        assert response.status_code == 403, f"{method} {path} expected 403"
        assert response.json()["detail"] == "Invalid or missing API key"


def test_health_does_not_require_api_key(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_valid_api_key_allows_review_queue(
    client: TestClient,
    auth_headers: dict[str, str],
    patch_pipeline,
) -> None:
    patch_pipeline(
        "list_review_queue",
        lambda self, **kwargs: ([sample_review_queue_row()], 1),
    )
    response = client.get("/api/v1/review-queue", headers=auth_headers)
    assert response.status_code == 200


def test_valid_api_key_allows_job_status(
    client: TestClient,
    auth_headers: dict[str, str],
    document_id,
    patch_pipeline,
) -> None:
    status = sample_job_status_response(document_id=document_id)
    patch_pipeline("build_job_status", lambda self, _: status)
    response = client.get(f"/api/v1/jobs/{document_id}", headers=auth_headers)
    assert response.status_code == 200


def test_login_returns_access_token(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "test-user", "password": "test-password"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0
    assert isinstance(body["access_token"], str) and body["access_token"]


def test_login_rejects_invalid_password(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "test-user", "password": "wrong-password"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


def test_login_does_not_require_api_key(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "test-user", "password": "test-password"},
    )
    assert response.status_code == 200


def test_bearer_token_allows_review_queue(
    client: TestClient,
    bearer_headers: dict[str, str],
    patch_pipeline,
) -> None:
    patch_pipeline(
        "list_review_queue",
        lambda self, **kwargs: ([sample_review_queue_row()], 1),
    )
    response = client.get("/api/v1/review-queue", headers=bearer_headers)
    assert response.status_code == 200


def test_invalid_bearer_token_rejected(client: TestClient) -> None:
    response = client.get(
        "/api/v1/review-queue",
        headers={"Authorization": "Bearer not-a-valid-token"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid token"


def test_expired_bearer_token_rejected(client: TestClient) -> None:
    settings = get_settings()
    expired_token = jwt.encode(
        {
            "sub": "test-user",
            "type": "access",
            "exp": 0,
            "iat": 0,
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    response = client.get(
        "/api/v1/review-queue",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Token has expired"


def test_login_unavailable_when_jwt_not_configured(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JWT_SECRET", "")
    get_settings.cache_clear()
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "test-user", "password": "test-password"},
    )
    assert response.status_code == 503
    get_settings.cache_clear()
    monkeypatch.setenv(
        "JWT_SECRET",
        "test-jwt-secret-at-least-32-characters-long",
    )
