"""Load Keith-editable thresholds from au_group_runtime_config when Supabase is configured."""

from __future__ import annotations

import logging
from typing import Any

import httpx
from app.core.config import Settings

logger = logging.getLogger(__name__)

_RUNTIME_KEYS: tuple[tuple[str, str], ...] = (
    ("creditor_name_min_length", "creditor_name_min_length"),
    ("creditor_line_number_max_digits", "creditor_line_number_max_digits"),
    ("creditor_dedup_threshold", "creditor_dedup_threshold"),
    ("creditor_dedup_enabled", "creditor_dedup_enabled"),
)


def _rpc_int(settings: Settings, name: str, key: str, default: int) -> int:
    url = settings.supabase_url.rstrip("/") + f"/rest/v1/rpc/{name}"
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }
    body = {"p_key": key, "p_default": default}
    with httpx.Client(timeout=settings.supabase_http_timeout_sec) as client:
        response = client.post(url, json=body, headers=headers)
        response.raise_for_status()
        data = response.json()
    if isinstance(data, int):
        return data
    if isinstance(data, str) and data.isdigit():
        return int(data)
    return default


def _rpc_bool(settings: Settings, key: str, default: bool) -> bool:
    url = settings.supabase_url.rstrip("/") + "/rest/v1/rpc/au_group_config_bool"
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }
    body = {"p_key": key, "p_default": default}
    with httpx.Client(timeout=settings.supabase_http_timeout_sec) as client:
        response = client.post(url, json=body, headers=headers)
        response.raise_for_status()
        data = response.json()
    if isinstance(data, bool):
        return data
    return default


def apply_runtime_config(settings: Settings) -> Settings:
    """Overlay env defaults with Supabase runtime_config when credentials exist."""
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return settings

    updates: dict[str, Any] = {}
    try:
        updates["creditor_name_min_length"] = _rpc_int(
            settings,
            "au_group_config_int",
            "creditor_name_min_length",
            settings.creditor_name_min_length,
        )
        updates["creditor_line_number_max_digits"] = _rpc_int(
            settings,
            "au_group_config_int",
            "creditor_line_number_max_digits",
            settings.creditor_line_number_max_digits,
        )
        updates["creditor_dedup_threshold"] = _rpc_int(
            settings,
            "au_group_config_int",
            "creditor_dedup_threshold",
            settings.creditor_dedup_threshold,
        )
        updates["creditor_dedup_enabled"] = _rpc_bool(
            settings,
            "creditor_dedup_enabled",
            settings.creditor_dedup_enabled,
        )
    except Exception:
        logger.warning("runtime_config_overlay_failed", exc_info=True)
        return settings

    return settings.model_copy(update=updates)
