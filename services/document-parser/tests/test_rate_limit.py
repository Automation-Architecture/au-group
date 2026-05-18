"""Rate limiting behavior (slowapi)."""

from slowapi.errors import RateLimitExceeded

from fastapi.testclient import TestClient

from app.core.rate_limit import limiter
from app.main import app
from tests.conftest import sample_parse_text_response


def test_rate_limit_exceeded_handler_registered() -> None:
    assert RateLimitExceeded in app.exception_handlers


def test_rate_limit_blocks_burst_parse_requests(
    client: TestClient,
    auth_headers: dict[str, str],
    patch_pipeline,
) -> None:
    was_enabled = limiter.enabled
    limiter.enabled = True
    try:
        patch_pipeline("parse_structured", lambda self, **kwargs: sample_parse_text_response())
        status_codes = [
            client.post(
                "/api/v1/parse/structured",
                json={"s3_key": "raw-documents/1/doc.pdf"},
                headers=auth_headers,
            ).status_code
            for _ in range(25)
        ]
        assert 429 in status_codes
    finally:
        limiter.enabled = was_enabled
        if hasattr(limiter, "reset"):
            limiter.reset()


def test_health_ready_endpoint_shape(client: TestClient, monkeypatch) -> None:
    import app.main as main_module

    monkeypatch.setattr(
        main_module,
        "run_readiness_checks",
        lambda _settings: {"supabase": "ok", "s3": "ok"},
    )
    response = client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["supabase"] == "ok"


def test_health_ready_returns_503_when_deps_fail(client: TestClient, monkeypatch) -> None:
    import app.main as main_module

    monkeypatch.setattr(
        main_module,
        "run_readiness_checks",
        lambda _settings: {"supabase": "supabase_unreachable", "s3": "ok"},
    )
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
