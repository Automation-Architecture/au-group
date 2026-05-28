"""Unit tests for Supabase runtime_config overlay (KD-69)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
from app.core.config import Settings
from app.core.runtime_config import _rpc_bool, _rpc_int, apply_runtime_config


def _settings_with_supabase() -> Settings:
    return Settings(
        api_key="x" * 32,
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="service-role-key",
        creditor_name_min_length=3,
        creditor_line_number_max_digits=4,
        creditor_dedup_threshold=85,
        creditor_dedup_enabled=True,
    )


def test_apply_runtime_config_skips_without_credentials() -> None:
    settings = Settings(api_key="x" * 32, supabase_url="", supabase_service_role_key="")
    assert apply_runtime_config(settings) is settings


def test_rpc_int_parses_string_digit_response() -> None:
    settings = _settings_with_supabase()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = "42"
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response

    with patch("app.core.runtime_config.httpx.Client", return_value=mock_client):
        assert (
            _rpc_int(settings, "au_group_config_int", "creditor_name_min_length", 3) == 42
        )


def test_rpc_int_returns_default_on_unexpected_shape() -> None:
    settings = _settings_with_supabase()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"unexpected": True}
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response

    with patch("app.core.runtime_config.httpx.Client", return_value=mock_client):
        assert _rpc_int(settings, "au_group_config_int", "some_key", 7) == 7


def test_rpc_bool_returns_default_on_non_bool() -> None:
    settings = _settings_with_supabase()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = "yes"
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response

    with patch("app.core.runtime_config.httpx.Client", return_value=mock_client):
        assert _rpc_bool(settings, "creditor_dedup_enabled", True) is True


def test_apply_runtime_config_overlays_all_keys() -> None:
    settings = _settings_with_supabase()

    def _fake_rpc_int(_s: Settings, _name: str, key: str, default: int) -> int:
        return {"creditor_name_min_length": 5, "creditor_line_number_max_digits": 6, "creditor_dedup_threshold": 90}[
            key
        ]

    with (
        patch("app.core.runtime_config._rpc_int", side_effect=_fake_rpc_int),
        patch("app.core.runtime_config._rpc_bool", return_value=False),
    ):
        updated = apply_runtime_config(settings)

    assert updated.creditor_name_min_length == 5
    assert updated.creditor_line_number_max_digits == 6
    assert updated.creditor_dedup_threshold == 90
    assert updated.creditor_dedup_enabled is False


def test_apply_runtime_config_returns_original_on_http_error() -> None:
    settings = _settings_with_supabase()
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.side_effect = httpx.HTTPError("network down")

    with patch("app.core.runtime_config.httpx.Client", return_value=mock_client):
        assert apply_runtime_config(settings).creditor_dedup_enabled is True
