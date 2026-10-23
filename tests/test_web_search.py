"""Tests for public web search, page fetch policy, and the LangChain tool."""

from __future__ import annotations

import pytest

from jarvis.infrastructure.web.fetch import fetch_public_page
from jarvis.infrastructure.web.policy import (
    UrlPolicyError,
    assert_fetchable_url,
    is_blocked_host,
)
from ddgs.exceptions import DDGSException, RatelimitException, TimeoutException

from jarvis.infrastructure.web.search import WebSearchError, search_public_web
from jarvis.tools.builtins.web_search import web_search_tool


def test_is_blocked_host_glassdoor_variants():
    assert is_blocked_host("www.glassdoor.com")
    assert is_blocked_host("glassdoor.es")
    assert is_blocked_host("jobs.glassdoor.com")
    assert not is_blocked_host("example.com")
    assert not is_blocked_host("notglassdoor.com")


def test_assert_fetchable_url_rejects_bad_scheme_and_glassdoor():
    with pytest.raises(UrlPolicyError, match="http and https"):
        assert_fetchable_url("ftp://example.com/a", check_robots=False)
    with pytest.raises(UrlPolicyError, match="Glassdoor"):
        assert_fetchable_url(
            "https://www.glassdoor.com/Reviews/Acme-Reviews-E1.htm",
            check_robots=False,
        )


def test_assert_fetchable_url_honors_robots(monkeypatch):
    def fake_robots(url: str, *, user_agent: str = "") -> bool:
        return False

    monkeypatch.setattr(
        "jarvis.infrastructure.web.policy.robots_txt_allows",
        fake_robots,
    )
    with pytest.raises(UrlPolicyError, match="robots.txt"):
        assert_fetchable_url("https://example.com/secret", check_robots=True)


def test_search_public_web_shape_and_clamp():
    raw = [
        {"title": "One", "href": "https://a.example/1", "body": "Snippet A"},
        {"title": "Two", "url": "https://b.example/2", "snippet": "Snippet B"},
        {"title": "Skip", "href": "", "body": "no url"},
    ]

    def fake_search(query: str, max_results: int) -> list[dict]:
        assert query == "acme careers"
        assert max_results == 10  # clamped from 99
        return raw

    results = search_public_web(
        "acme careers",
        max_results=99,
        search_fn=fake_search,
    )
    assert results == [
        {
            "title": "One",
            "url": "https://a.example/1",
            "snippet": "Snippet A",
        },
        {
            "title": "Two",
            "url": "https://b.example/2",
            "snippet": "Snippet B",
        },
    ]


def test_search_public_web_rejects_empty_query():
    with pytest.raises(ValueError, match="empty"):
        search_public_web("   ")


def test_fetch_public_page_extracts_text():
    html = "<html><head><title>Hello</title></head><body><p>World text</p></body></html>"

    class FakeResponse:
        status_code = 200
        url = "https://example.com/about"
        encoding = "utf-8"
        content = html.encode("utf-8")

        def raise_for_status(self) -> None:
            return None

    page = fetch_public_page(
        "https://example.com/about",
        check_robots=False,
        get_fn=lambda *args, **kwargs: FakeResponse(),
        extract_fn=lambda raw: "World text from page",
    )
    assert page["url"] == "https://example.com/about"
    assert page["text"] == "World text from page"


def test_fetch_public_page_truncates_long_text():
    class FakeResponse:
        status_code = 200
        url = "https://example.com/long"
        encoding = "utf-8"
        content = b"<html><body>x</body></html>"

        def raise_for_status(self) -> None:
            return None

    page = fetch_public_page(
        "https://example.com/long",
        check_robots=False,
        max_chars=20,
        get_fn=lambda *args, **kwargs: FakeResponse(),
        extract_fn=lambda raw: "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    )
    assert page["text"].endswith("…[truncated]")
    assert len(page["text"]) < 40


def test_fetch_rejects_redirect_to_glassdoor():
    class FakeResponse:
        status_code = 200
        url = "https://www.glassdoor.com/Job/1.htm"
        encoding = "utf-8"
        content = b"<html><body>paywall</body></html>"

        def raise_for_status(self) -> None:
            return None

    with pytest.raises(UrlPolicyError, match="Glassdoor"):
        fetch_public_page(
            "https://example.com/redirect",
            check_robots=False,
            get_fn=lambda *args, **kwargs: FakeResponse(),
            extract_fn=lambda raw: "should not run",
        )


def test_web_search_tool_query_only(monkeypatch):
    monkeypatch.setattr(
        "jarvis.tools.builtins.web_search.search_public_web",
        lambda query, max_results=5: [
            {
                "title": "Acme",
                "url": "https://acme.example/",
                "snippet": "Hiring engineers",
            }
        ],
    )
    monkeypatch.setattr(
        "jarvis.tools.builtins.web_search.fetch_public_page",
        lambda url: {
            "url": url,
            "title": "Acme careers",
            "text": "We are hiring engineers.",
        },
    )
    text = web_search_tool.invoke({"query": "Acme jobs", "url": ""})
    assert "## Search results" in text
    assert "https://acme.example/" in text
    assert "Hiring engineers" in text
    assert "## Fetched page" in text
    assert "We are hiring engineers." in text
    assert "stale" in text.lower()


def test_web_search_tool_fetch_top_zero_skips_auto_fetch(monkeypatch):
    monkeypatch.setattr(
        "jarvis.tools.builtins.web_search.search_public_web",
        lambda query, max_results=5: [
            {
                "title": "Acme",
                "url": "https://acme.example/",
                "snippet": "Hiring engineers",
            }
        ],
    )
    calls: list[str] = []

    def fake_fetch(url: str) -> dict[str, str]:
        calls.append(url)
        return {"url": url, "title": "x", "text": "y"}

    monkeypatch.setattr(
        "jarvis.tools.builtins.web_search.fetch_public_page",
        fake_fetch,
    )
    text = web_search_tool.invoke(
        {"query": "Acme jobs", "url": "", "fetch_top": 0}
    )
    assert calls == []
    assert "## Fetched page" not in text
    assert "https://acme.example/" in text


def test_web_search_tool_skips_blocked_then_fetches_next(monkeypatch):
    monkeypatch.setattr(
        "jarvis.tools.builtins.web_search.search_public_web",
        lambda query, max_results=5: [
            {
                "title": "Glassdoor",
                "url": "https://www.glassdoor.com/Reviews/x.htm",
                "snippet": "reviews",
            },
            {
                "title": "Official",
                "url": "https://example.com/season",
                "snippet": "Season 10.5",
            },
        ],
    )

    def fake_fetch(url: str) -> dict[str, str]:
        if "glassdoor" in url:
            raise UrlPolicyError("Glassdoor blocked")
        return {
            "url": url,
            "title": "Season hub",
            "text": "Current season is 10.5",
        }

    monkeypatch.setattr(
        "jarvis.tools.builtins.web_search.fetch_public_page",
        fake_fetch,
    )
    text = web_search_tool.invoke(
        {"query": "Marvel Rivals current season", "fetch_top": 1}
    )
    assert "Skipped page" in text
    assert "Current season is 10.5" in text



def test_web_search_tool_url_blocked():
    text = web_search_tool.invoke(
        {
            "query": "",
            "url": "https://www.glassdoor.com/Reviews/x.htm",
        }
    )
    assert text.startswith("Blocked by public-web policy:")
    assert "Glassdoor" in text


def test_web_search_tool_requires_input():
    text = web_search_tool.invoke({"query": "", "url": ""})
    assert "Provide a search query" in text


def test_search_public_web_retries_opaque_no_results_then_succeeds(monkeypatch):
    calls: list[str] = []
    sleeps: list[float] = []

    def fake(query: str, max_results: int, backend: str) -> list[dict]:
        calls.append(backend)
        assert query == "Marvel Rivals Season 9 features"
        if len(calls) < 3:
            raise DDGSException("No results found.")
        return [
            {
                "title": "Season 9",
                "href": "https://example.com/season-9",
                "body": "New features",
            }
        ]

    monkeypatch.setattr("jarvis.infrastructure.web.search._ddgs_text", fake)
    monkeypatch.setattr(
        "jarvis.infrastructure.web.search.time.sleep",
        lambda delay: sleeps.append(delay),
    )

    results = search_public_web("Marvel Rivals Season 9 features")
    assert results == [
        {
            "title": "Season 9",
            "url": "https://example.com/season-9",
            "snippet": "New features",
        }
    ]
    assert calls == [
        "auto",
        "brave,google,mojeek",
        "duckduckgo,yahoo,startpage,wikipedia",
    ]
    assert sleeps == [0.6, 1.5]


def test_search_public_web_reports_rate_limit_with_cause(monkeypatch):
    def fake(query: str, max_results: int, backend: str) -> list[dict]:
        raise DDGSException(RatelimitException("429 too many requests"))

    monkeypatch.setattr("jarvis.infrastructure.web.search._ddgs_text", fake)
    monkeypatch.setattr("jarvis.infrastructure.web.search.time.sleep", lambda delay: None)

    with pytest.raises(WebSearchError) as exc_info:
        search_public_web("Marvel Rivals Season 9 features")

    text = str(exc_info.value)
    assert text.startswith("Web lookup failed via ddgs.")
    assert "Exception: DDGSException:" in text
    assert "Cause: RatelimitException: 429 too many requests" in text
    assert "brave,google,mojeek" in text
    assert "rate limit" in text.lower()
    assert "No search results." not in text
    assert "no public information" in text


def test_search_public_web_timeout_hint(monkeypatch):
    def fake(query: str, max_results: int, backend: str) -> list[dict]:
        raise TimeoutException("timed out")

    monkeypatch.setattr("jarvis.infrastructure.web.search._ddgs_text", fake)
    monkeypatch.setattr("jarvis.infrastructure.web.search.time.sleep", lambda delay: None)

    with pytest.raises(WebSearchError) as exc_info:
        search_public_web("slow query")

    text = str(exc_info.value)
    assert "TimeoutException: timed out" in text
    assert "A search backend timed out." in text
    assert "No search results." not in text


def test_search_public_web_connection_hint_skips_duplicate_wrapper(monkeypatch):
    class ConnectError(OSError):
        """Stand-in for the HTTP client's connection error."""

    def fake(query: str, max_results: int, backend: str) -> list[dict]:
        inner = DDGSException("ConnectError: connection refused")
        raise DDGSException(inner) from ConnectError("connection refused")

    monkeypatch.setattr("jarvis.infrastructure.web.search._ddgs_text", fake)
    monkeypatch.setattr("jarvis.infrastructure.web.search.time.sleep", lambda delay: None)

    with pytest.raises(WebSearchError) as exc_info:
        search_public_web("Marvel Rivals Season 9 features")

    text = str(exc_info.value)
    assert "Exception: DDGSException: ConnectError: connection refused" in text
    assert "Cause: ConnectError: connection refused" in text
    assert "Could not reach a search backend" in text
    assert text.count("Exception: DDGSException:") == 1


def test_search_public_web_does_not_retry_unexpected_errors(monkeypatch):
    calls: list[str] = []

    def fake(query: str, max_results: int, backend: str) -> list[dict]:
        calls.append(backend)
        raise RuntimeError("parser blew up")

    monkeypatch.setattr("jarvis.infrastructure.web.search._ddgs_text", fake)

    with pytest.raises(WebSearchError) as exc_info:
        search_public_web("q")

    assert calls == ["auto"]
    text = str(exc_info.value)
    assert "RuntimeError: parser blew up" in text
    assert "brave,google,mojeek" not in text


def test_web_search_tool_empty_hits_are_not_provider_errors(monkeypatch):
    monkeypatch.setattr(
        "jarvis.tools.builtins.web_search.search_public_web",
        lambda query, max_results=5: [],
    )
    text = web_search_tool.invoke({"query": "nothing here", "fetch_top": 0})
    assert "No search results." in text
    assert "Web lookup failed" not in text
    assert "ddgs" not in text


def test_web_search_tool_returns_ddgs_error_text(monkeypatch):
    message = (
        "Web lookup failed via ddgs.\n"
        "- Exception: DDGSException: No results found.\n"
        "- Hint: provider failed"
    )

    def boom(query: str, max_results: int = 5) -> list[dict[str, str]]:
        raise WebSearchError(message)

    monkeypatch.setattr("jarvis.tools.builtins.web_search.search_public_web", boom)
    text = web_search_tool.invoke(
        {"query": "Marvel Rivals Season 9 features", "fetch_top": 2}
    )
    assert text == message
    assert "No search results." not in text


def test_web_search_tool_unexpected_error_includes_type_and_cause(monkeypatch):
    def boom(query: str, max_results: int = 5) -> list[dict[str, str]]:
        raise RuntimeError("parser blew up") from TimeoutError("socket timed out")

    monkeypatch.setattr("jarvis.tools.builtins.web_search.search_public_web", boom)
    text = web_search_tool.invoke({"query": "x", "fetch_top": 0})
    assert text.startswith("Web lookup failed.")
    assert "via ddgs" not in text
    assert "Exception: RuntimeError: parser blew up" in text
    assert "Cause: TimeoutError: socket timed out" in text
    assert "No search results." not in text


def test_web_search_tool_fetches_page(monkeypatch):
    monkeypatch.setattr(
        "jarvis.tools.builtins.web_search.fetch_public_page",
        lambda url: {
            "url": url,
            "title": "About",
            "text": "We build rockets.",
        },
    )
    text = web_search_tool.invoke(
        {"query": "", "url": "https://example.com/about"}
    )
    assert "## Fetched page" in text
    assert "We build rockets." in text
    assert "Cite this URL" in text
