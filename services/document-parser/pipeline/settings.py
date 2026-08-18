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

    # CourtListener / RECAP (Free Law Project) — free Form 204 retrieval source.
    # When set, intake tries the RECAP archive (free for archived docs) before
    # falling back to the paid PACER CM/ECF fetch. Empty = RECAP source disabled.
    courtlistener_api_token: str = ""
    courtlistener_timeout_sec: float = 30.0
    # Proactive pacing (KD-83). Discovery and Form 204 retrieval share ONE
    # account quota — measured live at 5/min, 50/hr on the authenticated REST
    # tier. 15s spacing is the interval proven to work; a burst of 5 is not.
    # run_call_budget caps a single intake run so an unattended cron stops
    # cleanly instead of grinding through hourly windows; cases it never reached
    # are left for the next run rather than recorded as misses.
    courtlistener_min_interval_sec: float = 15.0
    courtlistener_rate_per_min: int = 5
    courtlistener_rate_per_hour: int = 50
    courtlistener_run_call_budget: int = 45
    # Discovery's share of that budget, in pages (20 results/page). Capped so a
    # long backlog cannot spend the whole budget paginating and never reach a
    # single Form 204 lookup.
    courtlistener_discovery_page_budget: int = 12

    # BKwire CSV ingest — the confirmed PACER replacement (client, 2026-08-18).
    # The export carries no court district, no debtor state and no chapter, but
    # bankruptcies requires all three NOT NULL, so court_district/state are
    # sentinels and the chapter is written as 'unknown' (enum member added in
    # migration 20260818220000) rather than fabricated as '11'. Override only if
    # the feed is ever known to be single-chapter. See pipeline/bkwire.py.
    # bkwire_state_filter is a comma-separated list of CREDITOR states
    # ("NY,NJ,PA") and defaults to empty = keep everything: only 18% of the
    # sample export fell inside the old court-district scope, and the geography
    # question is still open with the client.
    bkwire_chapter_type: str = "unknown"
    bkwire_unknown_state: str = "XX"
    bkwire_state_filter: str = ""

    # Salesforce (salesforce_push stage — KD-68). Username/password + security
    # token (no Connected App / OAuth yet — MVP). Empty username/password ⇒ the
    # stage skips (guarded). domain='login' for production, 'test' for a sandbox.
    salesforce_username: str = ""
    salesforce_password: str = ""
    salesforce_security_token: str = ""
    salesforce_domain: str = "login"

    # ZoomInfo GTM API (zoom_info_enrich stage — KD-67). OAuth 2.0 client
    # credentials. Empty client id/secret ⇒ the stage is a no-op behind
    # SKIP_ENRICH (which is the real operational gate). match_status is the
    # minimum acceptable ZoomInfo matchStatus to trust an enrichment.
    zoominfo_client_id: str = ""
    zoominfo_client_secret: str = ""
    zoominfo_base_url: str = "https://api.zoominfo.com/gtm"
    zoominfo_timeout_sec: float = 30.0
    zoominfo_match_status: str = "FULL_MATCH"

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

    # Document-parser HTTP API (parse stage — KD-65). The worker calls the
    # document-parser web service over Railway private networking to OCR/parse
    # Form 204 PDFs.  DOCUMENT_PARSER_URL points at the web service's internal
    # address; DOCUMENT_PARSER_API_KEY is its X-API-Key (set as a Railway
    # reference variable to the web service's API_KEY).
    document_parser_url: str = "http://au-group.railway.internal:8080"
    document_parser_api_key: str = ""
    parse_poll_interval_sec: float = 5.0
    parse_poll_timeout_sec: float = 600.0   # 10 min ceiling per document
    parse_max_retries: int = 3              # transient httpx errors before giving up

    supabase_http_timeout_sec: float = 60.0
    app_env: str = "development"


_settings: PipelineSettings | None = None


def get_pipeline_settings() -> PipelineSettings:
    global _settings
    if _settings is None:
        _settings = PipelineSettings()
    return _settings
