"""DuckDuckGo-backed public web search (no API key)."""

from __future__ import annotations

from typing import Any, Callable

from ddgs import DDGS

DEFAULT_MAX_RESULTS = 5
HARD_MAX_RESULTS = 10


def _clamp_max_results(max_results: int) -> int:
    """Clamp ``max_results`` to a positive value at most ``HARD_MAX_RESULTS``."""
    if max_results < 1:
        return 1
    if max_results > HARD_MAX_RESULTS:
        return HARD_MAX_RESULTS
    return max_results


def search_public_web(
    query: str,
    *,
    max_results: int = DEFAULT_MAX_RESULTS,
    search_fn: Callable[[str, int], list[dict[str, Any]]] | None = None,
) -> list[dict[str, str]]:
    """
    Search the public web and return title, URL, and snippet rows.

    Uses DuckDuckGo via the ``ddgs`` package (no API key). Results may
    mention login-gated sites; Jarvis must not fetch those pages.

    Args:
        query: Search query string.
        max_results: Desired result count (clamped to 1..10).
        search_fn: Optional injectable search callable for tests. Receives
            ``(query, max_results)`` and returns raw result dicts.

    Returns:
        List of ``{"title", "url", "snippet"}`` dictionaries.

    Raises:
        ValueError: If ``query`` is empty after stripping.
    """
    cleaned = (query or "").strip()
    if not cleaned:
        raise ValueError("Search query is empty.")
    limit = _clamp_max_results(max_results)

    if search_fn is None:

        def search_fn(q: str, n: int) -> list[dict[str, Any]]:
            with DDGS() as client:
                return list(client.text(q, max_results=n))

    raw = search_fn(cleaned, limit)
    results: list[dict[str, str]] = []
    for item in raw:
        title = str(item.get("title") or "").strip()
        url = str(item.get("href") or item.get("url") or "").strip()
        snippet = str(item.get("body") or item.get("snippet") or "").strip()
        if not url:
            continue
        results.append({"title": title, "url": url, "snippet": snippet})
    return results
