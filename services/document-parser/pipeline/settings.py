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
    # Slack posting: bot token + channel ID (chat.postMessage).
    # SLACK_WEBHOOK_URL is NOT used — we switched from incoming webhooks to the
    # Slack bot API (chat.postMessage) so the bot can post to any channel it is
    # a member of without a per-channel webhook URL.  Set SLACK_BOT_TOKEN and
    # SLACK_CHANNEL_ID in the Railway service environment instead.
    slack_bot_token: str
    slack_channel_id: str  # e.g. C0B3PHV37SR for #au-group-sprint

    # PACER credentials (intake stage)
    pacer_username: str = ""
    pacer_password: str = ""

    # S3 (shared with document-parser web service)
    s3_bucket: str = "bankruptcy-creditor-docs"
    aws_region: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    s3_endpoint: str | None = None

    # Worker skip flags — disable blocked stages during parallel-run (KD-58)
    skip_enrich: bool = False   # SKIP_ENRICH=true disables zoom_info_enrich dispatch
    skip_sf: bool = False       # SKIP_SF=true disables salesforce_push dispatch
    worker_max_runtime_sec: int = 1500  # 25 min — exit before the 30-min cron interval

    supabase_http_timeout_sec: float = 60.0
    app_env: str = "development"


_settings: PipelineSettings | None = None


def get_pipeline_settings() -> PipelineSettings:
    global _settings
    if _settings is None:
        _settings = PipelineSettings()
    return _settings
