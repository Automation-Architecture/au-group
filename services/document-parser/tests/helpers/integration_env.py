"""Validate .env credentials required for live integration tests."""

from __future__ import annotations

import os
from dataclasses import dataclass

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class IntegrationEnv:
    settings: Settings
    bankruptcy_id: str | None
    run_id: str


REQUIRED_KEYS = (
    "API_KEY",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_ROLE_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "S3_BUCKET",
)


def integration_env_ready() -> tuple[bool, str]:
    missing = [key for key in REQUIRED_KEYS if not os.environ.get(key, "").strip()]
    if missing:
        return False, f"Missing .env keys: {', '.join(missing)}"
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return False, "Supabase URL or service role key empty"
    if not settings.aws_access_key_id or not settings.aws_secret_access_key:
        return False, "AWS credentials empty"
    return True, ""


def load_integration_env(run_id: str) -> IntegrationEnv:
    ready, reason = integration_env_ready()
    if not ready:
        raise RuntimeError(reason)
    settings = get_settings()
    bankruptcy_id = os.environ.get("INTEGRATION_BANKRUPTCY_ID", "").strip() or None
    return IntegrationEnv(
        settings=settings,
        bankruptcy_id=bankruptcy_id,
        run_id=run_id,
    )
