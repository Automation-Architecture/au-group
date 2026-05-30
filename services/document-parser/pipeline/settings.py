"""Minimal settings for standalone pipeline cron scripts.

Pipeline modules (report.py, worker.py, intake.py) are invoked as
``python -m pipeline.<module>`` from the service root.  They share the same
Railway env vars as the document-parser web service but do NOT require
API_KEY — that credential gates the HTTP API, not the queue workers.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_SERVICE_ROOT = Path(__file__).resolve().parents[1]
_ENV_FILE = _SERVICE_ROOT / ".env"


class PipelineSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE if _ENV_FILE.is_file() else None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    supabase_url: str
    supabase_service_role_key: str
    slack_webhook_url: str

    supabase_http_timeout_sec: float = 60.0
    app_env: str = "development"


_settings: PipelineSettings | None = None


def get_pipeline_settings() -> PipelineSettings:
    global _settings
    if _settings is None:
        _settings = PipelineSettings()
    return _settings
