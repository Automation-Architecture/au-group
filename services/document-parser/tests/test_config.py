import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


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
