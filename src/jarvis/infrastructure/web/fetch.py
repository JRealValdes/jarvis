"""Fetch public HTML pages and extract readable text."""

from __future__ import annotations

from typing import Any, Callable

import requests
import trafilatura

from jarvis.infrastructure.web.policy import USER_AGENT, assert_fetchable_url

DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_RESPONSE_BYTES = 500_000
MAX_EXTRACTED_CHARS = 8_000


def fetch_public_page(
    url: str,
    *,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = MAX_RESPONSE_BYTES,
    max_chars: int = MAX_EXTRACTED_CHARS,
    check_robots: bool = True,
    get_fn: Callable[..., Any] | None = None,
    extract_fn: Callable[[str], str | None] | None = None,
) -> dict[str, str]:
    """
    Download a public page and return extracted readable text.

    Only ``http``/``https`` are allowed. Blocked hosts (e.g. Glassdoor) and
    ``robots.txt`` disallows are rejected. No cookies or credentials are sent.

    Args:
        url: Absolute public URL.
        timeout_seconds: HTTP timeout for the page GET.
        max_bytes: Maximum response body size to keep before extraction.
        max_chars: Maximum characters of extracted text to return.
        check_robots: When True, honor robots.txt.
        get_fn: Optional injectable GET callable (tests). Signature like
            ``requests.get``.
        extract_fn: Optional injectable HTML→text extractor (tests).

    Returns:
        Dict with ``url``, ``title`` (may be empty), and ``text``.

    Raises:
        UrlPolicyError: If the URL fails policy checks.
        ValueError: If the response is empty or text cannot be extracted.
        requests.RequestException: On transport failures from ``requests``.
    """
    cleaned = assert_fetchable_url(url, check_robots=check_robots)
    http_get = get_fn or requests.get
    response = http_get(
        cleaned,
        timeout=timeout_seconds,
        headers={"User-Agent": USER_AGENT},
        allow_redirects=True,
    )
    response.raise_for_status()

    # Re-check final URL after redirects (scheme / blocked hosts).
    final_url = str(getattr(response, "url", cleaned) or cleaned)
    if final_url != cleaned:
        assert_fetchable_url(final_url, check_robots=check_robots)

    content: bytes = response.content or b""
    if len(content) > max_bytes:
        content = content[:max_bytes]
    html = content.decode(getattr(response, "encoding", None) or "utf-8", errors="replace")

    extractor = extract_fn or (lambda raw: trafilatura.extract(raw, include_comments=False))
    text = extractor(html)
    if not text or not str(text).strip():
        raise ValueError(
            "Could not extract readable text from the page "
            "(empty, blocked, or non-HTML content)."
        )
    body = str(text).strip()
    if len(body) > max_chars:
        body = body[:max_chars].rstrip() + "\n…[truncated]"

    title = ""
    if extract_fn is None:
        metadata = trafilatura.extract_metadata(html)
        if metadata is not None and getattr(metadata, "title", None):
            title = str(metadata.title).strip()

    return {
        "url": final_url,
        "title": title,
        "text": body,
    }
