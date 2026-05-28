"""Unit tests for readiness check helpers."""

from unittest.mock import MagicMock, patch

import httpx
from app.core.config import Settings
from app.core.readiness import check_s3, check_supabase, run_readiness_checks
from botocore.exceptions import ClientError


def test_check_supabase_not_configured() -> None:
    settings = Settings(
        api_key="test-key",
        supabase_url="",
        supabase_service_role_key="",
    )
    ok, detail = check_supabase(settings)
    assert ok is False
    assert detail == "supabase_not_configured"


def test_check_s3_not_configured() -> None:
    settings = Settings(
        api_key="test-key",
        aws_access_key_id=None,
        aws_secret_access_key=None,
    )
    ok, detail = check_s3(settings)
    assert ok is False
    assert detail == "s3_not_configured"


def test_run_readiness_checks_reports_both() -> None:
    settings = Settings(
        api_key="test-key",
        supabase_url="",
        supabase_service_role_key="",
        aws_access_key_id=None,
        aws_secret_access_key=None,
    )
    checks = run_readiness_checks(settings)
    assert "supabase" in checks
    assert "s3" in checks


def test_check_supabase_ok() -> None:
    settings = Settings(
        api_key="test-key",
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="key",
    )
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_response

    with patch("app.core.readiness.httpx.Client", return_value=mock_client):
        ok, detail = check_supabase(settings)
    assert ok is True
    assert detail == "ok"


def test_check_supabase_http_500() -> None:
    settings = Settings(
        api_key="test-key",
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="key",
    )
    mock_response = MagicMock()
    mock_response.status_code = 503
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.return_value = mock_response

    with patch("app.core.readiness.httpx.Client", return_value=mock_client):
        ok, detail = check_supabase(settings)
    assert ok is False
    assert detail == "supabase_http_503"


def test_check_supabase_unreachable() -> None:
    settings = Settings(
        api_key="test-key",
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="key",
    )
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.get.side_effect = httpx.ConnectError("refused")

    with patch("app.core.readiness.httpx.Client", return_value=mock_client):
        ok, detail = check_supabase(settings)
    assert ok is False
    assert detail == "supabase_unreachable"


def test_check_s3_ok() -> None:
    settings = Settings(
        api_key="test-key",
        aws_access_key_id="access",
        aws_secret_access_key="secret",
        s3_bucket="bankruptcy-creditor-docs",
    )
    mock_s3 = MagicMock()
    with patch("app.core.readiness.S3Client") as mock_client_cls:
        mock_client_cls.return_value._client = mock_s3
        ok, detail = check_s3(settings)
    assert ok is True
    assert detail == "ok"
    mock_s3.head_bucket.assert_called_once_with(Bucket="bankruptcy-creditor-docs")


def test_check_s3_client_error() -> None:
    settings = Settings(
        api_key="test-key",
        aws_access_key_id="access",
        aws_secret_access_key="secret",
    )
    error = ClientError(
        {"Error": {"Code": "403", "Message": "Forbidden"}},
        "HeadBucket",
    )
    mock_s3 = MagicMock()
    mock_s3.head_bucket.side_effect = error
    with patch("app.core.readiness.S3Client") as mock_client_cls:
        mock_client_cls.return_value._client = mock_s3
        ok, detail = check_s3(settings)
    assert ok is False
    assert detail == "s3_403"


def test_check_s3_generic_exception() -> None:
    settings = Settings(
        api_key="test-key",
        aws_access_key_id="access",
        aws_secret_access_key="secret",
    )
    mock_s3 = MagicMock()
    mock_s3.head_bucket.side_effect = RuntimeError("boom")
    with patch("app.core.readiness.S3Client") as mock_client_cls:
        mock_client_cls.return_value._client = mock_s3
        ok, detail = check_s3(settings)
    assert ok is False
    assert detail == "s3_unreachable"
