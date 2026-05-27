import pytest
from app.core.config import Settings, get_settings
from pydantic import ValidationError


def test_settings_rejects_empty_api_key() -> None:
    with pytest.raises(ValidationError):
        Settings(api_key="   ")


def test_get_settings_fails_fast_on_empty_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", "")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="API_KEY environment variable is required"):
        get_settings()
    get_settings.cache_clear()


def test_settings_reads_api_key_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", "secret-from-env")
    settings = Settings()
    assert settings.api_key == "secret-from-env"


def test_settings_supabase_http_timeout_default() -> None:
    settings = Settings(api_key="x" * 32)
    assert settings.supabase_http_timeout_sec == 60.0


def test_settings_supabase_http_timeout_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_HTTP_TIMEOUT_SEC", "90")
    settings = Settings(api_key="x" * 32)
    assert settings.supabase_http_timeout_sec == 90.0


def test_production_rejects_short_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(api_key="too-short", app_env="production")
    with pytest.raises(ValueError, match="at least 32"):
        settings.validate_api_key_strength()


def test_creditor_dedup_threshold_rejects_out_of_range() -> None:
    with pytest.raises(ValidationError):
        Settings(api_key="x" * 32, creditor_dedup_threshold=49)
    with pytest.raises(ValidationError):
        Settings(api_key="x" * 32, creditor_dedup_threshold=101)


def test_get_settings_surfaces_jwt_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("API_KEY", "x" * 32)
    monkeypatch.setenv("JWT_SECRET", "short")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="Invalid configuration"):
        get_settings()
    get_settings.cache_clear()
