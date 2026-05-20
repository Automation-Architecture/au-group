"""SSRF-safe HTTP URL validation and streaming downloads."""

from __future__ import annotations

import ipaddress
import socket
from pathlib import Path
from urllib.parse import urlparse, urljoin

import httpx

from app.core.http_download import browser_like_headers

_BLOCKED_SCHEMES = frozenset({"file", "ftp", "gopher", "data", "javascript"})


def _parse_host_suffixes(raw: str) -> tuple[str, ...]:
    return tuple(s.strip().lower().lstrip(".") for s in raw.split(",") if s.strip())


def _hostname_allowed(hostname: str, allowed_suffixes: tuple[str, ...]) -> bool:
    host = hostname.lower().rstrip(".")
    if not host:
        return False
    for suffix in allowed_suffixes:
        if host == suffix or host.endswith(f".{suffix}"):
            return True
    return False


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or (isinstance(ip, ipaddress.IPv4Address) and ip in ipaddress.ip_network("169.254.0.0/16"))
    )


def _resolve_host_ips(hostname: str) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    if not hostname:
        return []
    try:
        literal = ipaddress.ip_address(hostname)
        return [literal]
    except ValueError:
        pass
    ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for family, _, _, _, sockaddr in socket.getaddrinfo(
        hostname, None, type=socket.SOCK_STREAM
    ):
        addr = sockaddr[0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if family == socket.AF_INET6 and isinstance(ip, ipaddress.IPv6Address):
            if ip.ipv4_mapped:
                ip = ip.ipv4_mapped
        ips.append(ip)
    return ips


def assert_safe_download_url(
    url: str,
    *,
    allow_document_url: bool,
    allowed_host_suffixes: tuple[str, ...],
    require_https: bool,
) -> None:
    if not allow_document_url:
        raise ValueError("document_url downloads are disabled")

    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme in _BLOCKED_SCHEMES:
        raise ValueError("URL scheme is not allowed")
    if scheme not in {"http", "https"}:
        raise ValueError("Only http and https URLs are allowed")
    if require_https and scheme != "https":
        raise ValueError("Only https URLs are allowed")
    if parsed.username or parsed.password:
        raise ValueError("URLs with embedded credentials are not allowed")
    if not parsed.hostname:
        raise ValueError("URL must include a hostname")

    if not allowed_host_suffixes:
        raise ValueError("No download hosts are configured")

    resolved_ips = _resolve_host_ips(parsed.hostname)
    for ip in resolved_ips:
        if _is_blocked_ip(ip):
            raise ValueError("Download host resolves to a non-public address")

    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        pass
    else:
        raise ValueError("Literal IP addresses are not allowed")

    if not _hostname_allowed(parsed.hostname, allowed_host_suffixes):
        raise ValueError("Download host is not allowed")


def download_url_to_path(
    url: str,
    dest: Path,
    *,
    max_bytes: int,
    timeout_sec: float,
    max_redirects: int,
    allow_document_url: bool,
    allowed_host_suffixes: tuple[str, ...],
    require_https: bool,
) -> None:
    assert_safe_download_url(
        url,
        allow_document_url=allow_document_url,
        allowed_host_suffixes=allowed_host_suffixes,
        require_https=require_https,
    )
    headers = browser_like_headers(url)
    current = url
    total_written = 0

    try:
        with httpx.Client(follow_redirects=False, timeout=timeout_sec, headers=headers) as client:
            for _ in range(max_redirects + 1):
                assert_safe_download_url(
                    current,
                    allow_document_url=allow_document_url,
                    allowed_host_suffixes=allowed_host_suffixes,
                    require_https=require_https,
                )
                with client.stream("GET", current) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise ValueError("Redirect response missing Location header")
                        current = urljoin(current, location)
                        continue
                    try:
                        response.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        status = exc.response.status_code
                        if status == 404:
                            raise FileNotFoundError("Document not found at URL") from exc
                        if status in {401, 403}:
                            raise PermissionError("Access denied downloading document") from exc
                        raise ValueError("Failed to download document") from exc
                    with dest.open("wb") as handle:
                        for chunk in response.iter_bytes():
                            total_written += len(chunk)
                            if total_written > max_bytes:
                                raise ValueError("Download exceeds size limit")
                            handle.write(chunk)
                    return
    except httpx.HTTPError as exc:
        if isinstance(exc, httpx.HTTPStatusError):
            raise
        raise ValueError("Failed to download document") from exc

    raise ValueError("Too many redirects")
