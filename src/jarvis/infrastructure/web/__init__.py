"""Public-web search and page reading helpers."""

from jarvis.infrastructure.web.fetch import fetch_public_page
from jarvis.infrastructure.web.policy import (
    UrlPolicyError,
    assert_fetchable_url,
    is_blocked_host,
)
from jarvis.infrastructure.web.search import search_public_web

__all__ = [
    "UrlPolicyError",
    "assert_fetchable_url",
    "fetch_public_page",
    "is_blocked_host",
    "search_public_web",
]
