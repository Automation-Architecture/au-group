from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_parse_requires_api_key() -> None:
    response = client.post("/api/v1/parse/structured", json={"s3_key": "test.pdf"})
    assert response.status_code == 403


def test_parse_structured_rejects_without_s3() -> None:
    settings = get_settings()
    response = client.post(
        "/api/v1/parse/structured",
        json={},
        headers={"X-API-Key": settings.api_key},
    )
    assert response.status_code == 400
    assert "s3_key" in response.json()["detail"]
