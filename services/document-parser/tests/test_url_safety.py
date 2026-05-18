"""SSRF and download safety tests."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.core.url_safety import assert_safe_download_url, download_url_to_path


def test_blocks_metadata_ip() -> None:
    with pytest.raises(ValueError, match="non-public"):
        assert_safe_download_url(
            "http://169.254.169.254/latest/meta-data/",
            allow_document_url=True,
            allowed_host_suffixes=("example.com",),
            require_https=False,
        )


def test_blocks_loopback() -> None:
    with pytest.raises(ValueError, match="non-public"):
        assert_safe_download_url(
            "http://127.0.0.1/file.pdf",
            allow_document_url=True,
            allowed_host_suffixes=("example.com",),
            require_https=False,
        )


def test_blocks_when_document_url_disabled() -> None:
    with pytest.raises(ValueError, match="disabled"):
        assert_safe_download_url(
            "https://example.com/doc.pdf",
            allow_document_url=False,
            allowed_host_suffixes=("example.com",),
            require_https=False,
        )


def test_blocks_host_not_on_allowlist() -> None:
    with (
        patch(
            "app.core.url_safety.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
        ),
        pytest.raises(ValueError, match="not allowed"),
    ):
        assert_safe_download_url(
            "https://evil.example.net/doc.pdf",
            allow_document_url=True,
            allowed_host_suffixes=("example.com",),
            require_https=False,
        )


def test_allows_configured_suffix() -> None:
    with patch(
        "app.core.url_safety.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("93.184.216.34", 0))],
    ):
        assert_safe_download_url(
            "https://docs.uscourts.gov/file.pdf",
            allow_document_url=True,
            allowed_host_suffixes=("uscourts.gov",),
            require_https=True,
        )


def test_requires_https_in_production_mode() -> None:
    with pytest.raises(ValueError, match="https"):
        assert_safe_download_url(
            "http://uscourts.gov/file.pdf",
            allow_document_url=True,
            allowed_host_suffixes=("uscourts.gov",),
            require_https=True,
        )


def test_download_enforces_size_limit(tmp_path: Path) -> None:
    dest = tmp_path / "out.pdf"

    def _fake_stream(*_args, **_kwargs):
        response = MagicMock()
        response.is_redirect = False
        response.raise_for_status = MagicMock()
        response.iter_bytes = lambda: [b"x" * 1024]
        return response

    mock_client = MagicMock()
    mock_client.stream.return_value.__enter__ = lambda *_: _fake_stream()
    mock_client.stream.return_value.__exit__ = MagicMock(return_value=False)
    mock_client.__enter__ = lambda self: self
    mock_client.__exit__ = MagicMock(return_value=False)

    with (
        patch("app.core.url_safety.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]),
        patch("app.core.url_safety.httpx.Client", return_value=mock_client),
        pytest.raises(ValueError, match="size limit"),
    ):
        download_url_to_path(
            "https://example.com/large.pdf",
            dest,
            max_bytes=512,
            timeout_sec=5.0,
            max_redirects=0,
            allow_document_url=True,
            allowed_host_suffixes=("example.com",),
            require_https=True,
        )


def test_download_maps_404_to_file_not_found(tmp_path: Path) -> None:
    dest = tmp_path / "out.pdf"
    request = httpx.Request("GET", "https://example.com/missing.pdf")
    response = httpx.Response(404, request=request)

    mock_response = MagicMock()
    mock_response.is_redirect = False
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "not found", request=request, response=response
    )

    mock_client = MagicMock()
    mock_client.stream.return_value.__enter__ = MagicMock(return_value=mock_response)
    mock_client.stream.return_value.__exit__ = MagicMock(return_value=False)
    mock_client.__enter__ = lambda self: self
    mock_client.__exit__ = MagicMock(return_value=False)

    with (
        patch("app.core.url_safety.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 0))]),
        patch("app.core.url_safety.httpx.Client", return_value=mock_client),
        pytest.raises(FileNotFoundError),
    ):
        download_url_to_path(
            "https://example.com/missing.pdf",
            dest,
            max_bytes=1_000_000,
            timeout_sec=5.0,
            max_redirects=0,
            allow_document_url=True,
            allowed_host_suffixes=("example.com",),
            require_https=True,
        )
