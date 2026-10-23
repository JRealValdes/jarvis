"""LangChain tool for public web search and page reading."""

from __future__ import annotations

import logging

from langchain_core.tools import tool

from jarvis.infrastructure.web.fetch import fetch_public_page
from jarvis.infrastructure.web.policy import UrlPolicyError
from jarvis.infrastructure.web.search import (
    DEFAULT_MAX_RESULTS,
    WebSearchError,
    search_public_web,
)

logger = logging.getLogger(__name__)

DEFAULT_FETCH_TOP = 2
HARD_MAX_FETCH_TOP = 3


def _clamp_fetch_top(fetch_top: int) -> int:
    """Clamp ``fetch_top`` to ``0..HARD_MAX_FETCH_TOP``."""
    if fetch_top < 0:
        return 0
    if fetch_top > HARD_MAX_FETCH_TOP:
        return HARD_MAX_FETCH_TOP
    return fetch_top


def _format_search_results(results: list[dict[str, str]]) -> str:
    """Format search hits as a numbered markdown list."""
    if not results:
        return "No search results."
    lines = ["## Search results"]
    for index, item in enumerate(results, start=1):
        title = item.get("title") or "(no title)"
        url = item.get("url") or ""
        snippet = item.get("snippet") or ""
        lines.append(f"{index}. **{title}**")
        lines.append(f"   - URL: {url}")
        if snippet:
            lines.append(f"   - Snippet: {snippet}")
    return "\n".join(lines)


def _format_page(page: dict[str, str]) -> str:
    """Format a fetched page for the agent."""
    title = page.get("title") or "(no title)"
    url = page.get("url") or ""
    text = page.get("text") or ""
    return (
        "## Fetched page\n"
        f"- Title: {title}\n"
        f"- URL: {url}\n\n"
        f"{text}\n\n"
        "Cite this URL when using facts from the page."
    )


def _fetch_top_search_pages(
    results: list[dict[str, str]],
    fetch_top: int,
) -> list[str]:
    """
    Fetch readable text from the first successful search hit URLs.

    Args:
        results: Search rows with ``url`` keys.
        fetch_top: Maximum number of successful page fetches.

    Returns:
        Formatted page sections (and skip notes for failed attempts).
    """
    limit = _clamp_fetch_top(fetch_top)
    if limit <= 0 or not results:
        return []

    sections: list[str] = []
    success = 0
    attempts = 0
    max_attempts = min(len(results), max(limit * 2, limit))
    seen: set[str] = set()

    for item in results:
        if success >= limit or attempts >= max_attempts:
            break
        url = (item.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        attempts += 1
        try:
            page = fetch_public_page(url)
            sections.append(_format_page(page))
            success += 1
        except (UrlPolicyError, Exception) as exc:
            sections.append(
                f"## Skipped page\n- URL: {url}\n- Reason: {exc}"
            )
    return sections


@tool
def web_search_tool(
    query: str = "",
    url: str = "",
    max_results: int = DEFAULT_MAX_RESULTS,
    fetch_top: int = DEFAULT_FETCH_TOP,
) -> str:
    """
    Search the public web and/or read the text of a public page.

    Use when the answer needs current information about a company, role,
    product, game version/season, or public posting that the user did not
    paste. Pass a search query, a URL, or both.

    For "current / now / latest / which version / which season" questions:
    use a focused query (include the topic and words like "current season"
    or "latest patch"), keep fetch_top at least 2 so page bodies are read,
    and prefer official sites. Search snippets alone are often outdated—
    ground answers in fetched page text and cite URLs. If sources conflict,
    say so. Pair with current_date_time_tool when recency matters.

    Public pages only: http/https, no login, no cookies, no credentialed
    sites. Honors robots.txt. Does not fetch Glassdoor or similar
    login-gated job boards (search snippets that mention them are OK).
    Do not bypass captchas, paywalls, or bot checks.

    Parameters:
    - query: optional web search query
    - url: optional absolute http(s) URL to fetch and read
    - max_results: search hit count (default 5, max 10)
    - fetch_top: after a search, fetch readable text from up to this many
      hit URLs (default 2, max 3; use 0 for snippets only)
    """
    cleaned_query = (query or "").strip()
    cleaned_url = (url or "").strip()
    if not cleaned_query and not cleaned_url:
        return (
            "Provide a search query and/or a public http(s) URL. "
            "Example: query='Acme Corp engineering blog', "
            "or url='https://example.com/about'."
        )

    sections: list[str] = []
    try:
        if cleaned_query:
            results = search_public_web(cleaned_query, max_results=max_results)
            sections.append(_format_search_results(results))
            sections.append(
                "Snippets can be stale. Prefer facts from Fetched page "
                "sections below. Prefer official sites and the newest dated "
                "sources. If sources conflict, say so and cite URLs. "
                "Do not fetch Glassdoor or other blocked job boards."
            )
            sections.extend(_fetch_top_search_pages(results, fetch_top))
        if cleaned_url:
            page = fetch_public_page(cleaned_url)
            sections.append(_format_page(page))
    except UrlPolicyError as exc:
        return f"Blocked by public-web policy: {exc}"
    except WebSearchError as exc:
        logger.warning("web_search_tool provider failure:\n%s", exc)
        return str(exc)
    except Exception as exc:
        message = _format_unexpected_lookup_failure(exc)
        logger.warning("web_search_tool failed: %s", message, exc_info=exc)
        return message

    return "\n\n".join(sections)


def _format_unexpected_lookup_failure(exc: BaseException) -> str:
    """Format a non-ddgs lookup error with type, cause, and a retry hint.

    Args:
        exc: Exception raised while searching or fetching a page.

    Returns:
        Multi-line failure text for the agent and for operators.
    """
    lines = [
        "Web lookup failed.",
        f"- Exception: {type(exc).__name__}: {exc}",
    ]
    cause = exc.__cause__
    if cause is None and exc.args and isinstance(exc.args[0], BaseException):
        cause = exc.args[0]
    if isinstance(cause, BaseException):
        lines.append(f"- Cause: {type(cause).__name__}: {cause}")
    lines.append(
        "- Hint: Retry the request. Tell the user the lookup failed, "
        "not that the topic has no public information."
    )
    return "\n".join(lines)
