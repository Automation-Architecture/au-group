from app.core.http_download import browser_like_headers


def test_browser_like_headers_includes_sec_fetch_and_referer() -> None:
    url = "https://example.com/path/doc.pdf"
    headers = browser_like_headers(url)

    assert "Mozilla" in headers["User-Agent"]
    assert headers["Referer"] == "https://example.com/"
    assert headers["Origin"] == "https://example.com"
    assert headers["Sec-Fetch-Dest"] == "document"
    assert "application/pdf" in headers["Accept"]
