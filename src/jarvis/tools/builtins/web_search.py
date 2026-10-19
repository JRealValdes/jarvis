"""LangChain tool for public web search and page reading."""

from __future__ import annotations

from langchain_core.tools import tool

from jarvis.infrastructure.web.fetch import fetch_public_page
from jarvis.infrastructure.web.policy import UrlPolicyError
from jarvis.infrastructure.web.search import DEFAULT_MAX_RESULTS, search_public_web


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


@tool
def web_search_tool(
    query: str = "",
    url: str = "",
    max_results: int = DEFAULT_MAX_RESULTS,
) -> str:
    """
    Search the public web and/or read the text of a public page.

    Use when the answer needs current information about a company, role,
    product, or public posting that the user did not paste. Pass a search
    query, a URL, or both. Returns search hits (title, URL, snippet) and,
    when a URL is provided, extracted readable text.

    Public pages only: http/https, no login, no cookies, no credentialed
    sites. Honors robots.txt. Does not fetch Glassdoor or similar
    login-gated job boards (search snippets that mention them are OK).
    Do not bypass captchas, paywalls, or bot checks. Always cite the URL
    you used.

    Parameters:
    - query: optional web search query
    - url: optional absolute http(s) URL to fetch and read
    - max_results: search hit count (default 5, max 10)
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
                "Search snippets may mention login-gated sites; do not "
                "fetch Glassdoor or other blocked job boards."
            )
        if cleaned_url:
            page = fetch_public_page(cleaned_url)
            sections.append(_format_page(page))
    except UrlPolicyError as exc:
        return f"Blocked by public-web policy: {exc}"
    except Exception as exc:
        return f"Web lookup failed: {exc}"

    return "\n\n".join(sections)
