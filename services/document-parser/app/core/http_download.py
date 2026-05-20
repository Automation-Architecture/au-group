"""HTTP fetch helpers for document_url downloads (anti-bot friendly headers)."""

from urllib.parse import urlparse

# Modern Chrome on macOS — reduces 403 from basic bot filters (not full Cloudflare JS challenges).
_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


def browser_like_headers(document_url: str, *, user_agent: str | None = None) -> dict[str, str]:
    """Headers that mimic a normal browser navigation to a PDF/document URL."""
    parsed = urlparse(document_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    referer = f"{origin}/" if parsed.netloc else document_url

    return {
        "User-Agent": user_agent or _DEFAULT_USER_AGENT,
        "Accept": "application/pdf,application/octet-stream,application/xhtml+xml,text/html;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": referer,
        "Origin": origin,
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-User": "?1",
        "Sec-CH-UA": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": '"macOS"',
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "DNT": "1",
    }
