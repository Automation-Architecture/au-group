from fastapi.testclient import TestClient

from app.core.config import get_settings


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "parser_version" in body


def test_health_response_shape(client: TestClient) -> None:
    response = client.get("/health")
    body = response.json()
    assert set(body.keys()) == {"status", "parser_version"}
    assert "api_key" not in body


def test_parse_requires_api_key(client: TestClient) -> None:
    response = client.post("/api/v1/parse/structured", json={"s3_key": "test.pdf"})
    assert response.status_code == 403


def test_parse_structured_rejects_without_s3(client: TestClient) -> None:
    settings = get_settings()
    response = client.post(
        "/api/v1/parse/structured",
        json={},
        headers={"X-API-Key": settings.api_key},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid request"


def test_s3_missing_object_returns_404(client: TestClient, patch_pipeline) -> None:
    settings = get_settings()

    def _raise_not_found(self, **_kwargs: object) -> None:
        raise FileNotFoundError("S3 object not found: missing.pdf")

    patch_pipeline("parse_ocr", _raise_not_found)
    response = client.post(
        "/api/v1/parse/ocr",
        json={"s3_key": "raw-documents/24-10001/missing.pdf"},
        headers={"X-API-Key": settings.api_key},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Not found"
