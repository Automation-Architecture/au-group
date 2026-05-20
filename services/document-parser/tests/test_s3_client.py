from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.core.config import Settings
from app.persistence.s3 import S3Client, _client_error_to_exception


def test_s3_client_uses_supabase_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_KEY", "test-key")
    settings = Settings(
        api_key="test-key",
        s3_endpoint="https://example.storage.supabase.co/storage/v1/s3",
        aws_region="ap-southeast-1",
        aws_access_key_id="access",
        aws_secret_access_key="secret",
        s3_bucket="bankruptcy-creditor-docs",
    )
    with patch("app.persistence.s3.get_settings", return_value=settings):
        with patch("app.persistence.s3.boto3.client") as mock_client:
            S3Client()
    mock_client.assert_called_once_with(
        "s3",
        region_name="ap-southeast-1",
        endpoint_url="https://example.storage.supabase.co/storage/v1/s3",
        aws_access_key_id="access",
        aws_secret_access_key="secret",
    )


def test_client_error_maps_not_found() -> None:
    exc = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "not found"}},
        "GetObject",
    )
    mapped = _client_error_to_exception(exc, "missing.pdf")
    assert isinstance(mapped, FileNotFoundError)


def test_client_error_maps_access_denied() -> None:
    exc = ClientError(
        {"Error": {"Code": "403", "Message": "Forbidden"}},
        "GetObject",
    )
    mapped = _client_error_to_exception(exc, "secret.pdf")
    assert isinstance(mapped, PermissionError)


def test_download_to_temp_raises_file_not_found() -> None:
    settings = Settings(
        api_key="test-key",
        s3_endpoint="https://example.storage.supabase.co/storage/v1/s3",
        aws_access_key_id="access",
        aws_secret_access_key="secret",
    )
    client_error = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "not found"}},
        "GetObject",
    )
    mock_boto = MagicMock()
    mock_boto.download_file.side_effect = client_error
    with patch("app.persistence.s3.get_settings", return_value=settings):
        with patch("app.persistence.s3.boto3.client", return_value=mock_boto):
            client = S3Client()
            with pytest.raises(FileNotFoundError):
                client.download_to_temp("raw-documents/24-10001/missing.pdf")
