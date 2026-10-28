"""Public web search via the ``ddgs`` metasearch package (no API key)."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable
from urllib.parse import urlparse

from ddgs import DDGS
from ddgs.exceptions import DDGSException, RatelimitException, TimeoutException

logger = logging.getLogger(__name__)

DEFAULT_MAX_RESULTS = 5
HARD_MAX_RESULTS = 10
DEFAULT_IMAGE_RESULTS = 3
HARD_MAX_IMAGE_RESULTS = 3
MAX_INLINE_IMAGES_PER_REPLY = 1
_IMAGE_EXTENSIONS = (".gif", ".jpeg", ".jpg", ".png", ".webp")
_PREFERRED_IMAGE_HOSTS = (
    "commons.wikimedia.org",
    "upload.wikimedia.org",
    "wikipedia.org",
)

# Library default is 5s, which is tight on a slow link. Match the ddgs HTTP
# client default so a single slow backend is less likely to look like "no results".
_DDGS_TIMEOUT_SECONDS = 10
_BACKOFF_SECONDS = (0.6, 1.5)
# ``auto`` already mixes engines, but a home or shared IP (typical on the Pi)
# often gets an empty raise from that mix. Later attempts pin other backends.
_BACKEND_ATTEMPTS = (
    "auto",
    "brave,google,mojeek",
    "duckduckgo,yahoo,startpage,wikipedia",
)
_MODEL_GUIDANCE = (
    "Tell the user the web search failed and that they can retry. "
    "Do not treat this as proof that the topic has no public information."
)


class WebSearchError(Exception):
    """Search provider failed.

    The message names ``ddgs``, the exception type, the backends tried, and a
    short hint. A successful search that returns zero hits does not raise.
    """


def _clamp_max_results(max_results: int) -> int:
    """Clamp ``max_results`` to a positive value at most ``HARD_MAX_RESULTS``."""
    if max_results < 1:
        return 1
    if max_results > HARD_MAX_RESULTS:
        return HARD_MAX_RESULTS
    return max_results


def _exception_chain(exc: BaseException) -> list[BaseException]:
    """Return ``exc`` plus its cause, including ddgs' wrapped ``args[0]``."""
    chain: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        nested: BaseException | None = None
        if current.__cause__ is not None:
            nested = current.__cause__
        elif current.args and isinstance(current.args[0], BaseException):
            # ddgs does ``raise DDGSException(err)`` without ``from err``.
            nested = current.args[0]
        elif current.__context__ is not None and not current.__suppress_context__:
            nested = current.__context__
        current = nested
    return chain


def _hint_for(exc: BaseException) -> str:
    """Classify a ddgs failure so the model and operators know how to react."""
    chain = _exception_chain(exc)
    type_names = {type(part).__name__ for part in chain}
    text = " ".join(str(part) for part in chain).lower()
    if (
        "RatelimitException" in type_names
        or "rate limit" in text
        or "ratelimit" in text
        or "429" in text
    ):
        detail = (
            "Likely a rate limit from a search backend. Wait briefly and retry. "
            "Shared or home IPs, including a Raspberry Pi, are throttled more "
            "often than a desktop browser."
        )
    elif (
        "TimeoutException" in type_names
        or "timed out" in text
        or "timeout" in text
    ):
        detail = (
            "A search backend timed out. Retry the same query. "
            "Slow links can hit the ddgs request timeout."
        )
    elif "no results found" in text:
        detail = (
            "ddgs raised an empty-result error. That usually means a backend "
            "was rate-limited, blocked, or flaky, not that the topic has no "
            "pages. A successful search with zero hits is reported as "
            "'No search results.' and does not use this error."
        )
    elif any(
        "Connect" in name or name in {"ConnectionError", "OSError"}
        for name in type_names
    ) or "connecterror" in text or "connection refused" in text or "network" in text:
        detail = (
            "Could not reach a search backend (connection refused, proxy, or "
            "firewall). Retry after checking outbound HTTPS from this host."
        )
    else:
        detail = (
            "The search provider failed. Retry the query. If this keeps "
            "happening, check outbound HTTPS from this host."
        )
    return f"{detail} {_MODEL_GUIDANCE}"


def format_search_failure(exc: BaseException, *, backends: list[str]) -> str:
    """Build the tool-facing message for a ddgs failure.

    Args:
        exc: Exception raised by ``ddgs`` or by the retry loop.
        backends: Backend names tried, in order.

    Returns:
        Multi-line failure text. Distinct from a successful empty result list.
    """
    chain = _exception_chain(exc)
    shown: list[BaseException] = []
    for part in chain:
        if shown and type(part) is type(shown[-1]) and str(part) == str(shown[-1]):
            continue
        shown.append(part)
        if len(shown) == 3:
            break
    labels = ("Exception", "Cause", "Earlier")
    lines = ["Web lookup failed via ddgs."]
    lines.extend(
        f"- {label}: {type(part).__name__}: {part}"
        for label, part in zip(labels, shown)
    )
    tried = "; ".join(backends) if backends else "auto"
    lines.append(f"- Backends tried: {tried}")
    lines.append(f"- Hint: {_hint_for(exc)}")
    return "\n".join(lines)


def _is_transient(exc: BaseException) -> bool:
    """Return whether another backend attempt is worth making."""
    chain = _exception_chain(exc)
    transient = (
        DDGSException,
        RatelimitException,
        TimeoutException,
        TimeoutError,
        ConnectionError,
        OSError,
    )
    return any(isinstance(part, transient) for part in chain)


def _ddgs_text(query: str, max_results: int, backend: str) -> list[dict[str, Any]]:
    """Run one ``ddgs`` text search against ``backend``."""
    with DDGS(timeout=_DDGS_TIMEOUT_SECONDS) as client:
        return list(client.text(query, max_results=max_results, backend=backend))


def _search_with_retries(
    query: str,
    max_results: int,
    runner: Callable[[str, int, str], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Run ``runner`` across backends until one attempt succeeds.

    Args:
        query: Non-empty search query.
        max_results: Clamped hit count passed through to ``ddgs``.
        runner: One backend call, ``(query, max_results, backend)``.

    Returns:
        Raw result dicts from the first successful attempt.

    Raises:
        WebSearchError: If every attempt fails, or a non-transient error occurs.
    """
    last_exc: BaseException | None = None
    tried: list[str] = []
    for attempt, backend in enumerate(_BACKEND_ATTEMPTS):
        tried.append(backend)
        try:
            return runner(query, max_results, backend)
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "ddgs search failed query=%r attempt %s/%s backend=%s: %s: %s",
                query,
                attempt + 1,
                len(_BACKEND_ATTEMPTS),
                backend,
                type(exc).__name__,
                exc,
            )
            if attempt >= len(_BACKEND_ATTEMPTS) - 1 or not _is_transient(exc):
                break
            time.sleep(_BACKOFF_SECONDS[min(attempt, len(_BACKOFF_SECONDS) - 1)])
    assert last_exc is not None
    raise WebSearchError(format_search_failure(last_exc, backends=tried)) from last_exc


def _search_ddgs(query: str, max_results: int) -> list[dict[str, Any]]:
    """Search text via ``ddgs``, retrying transient failures on alternate backends."""
    return _search_with_retries(query, max_results, _ddgs_text)


def _ddgs_images(query: str, max_results: int, backend: str) -> list[dict[str, Any]]:
    """Run one ``ddgs`` image search against ``backend``."""
    with DDGS(timeout=_DDGS_TIMEOUT_SECONDS) as client:
        return list(client.images(query, max_results=max_results, backend=backend))


def _search_ddgs_images(query: str, max_results: int) -> list[dict[str, Any]]:
    """Search images via ``ddgs``, retrying transient failures on alternate backends."""
    return _search_with_retries(query, max_results, _ddgs_images)


def _normalize_hits(raw: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Map provider rows to ``title``, ``url``, and ``snippet``."""
    results: list[dict[str, str]] = []
    for item in raw:
        title = str(item.get("title") or "").strip()
        url = str(item.get("href") or item.get("url") or "").strip()
        snippet = str(item.get("body") or item.get("snippet") or "").strip()
        if not url:
            continue
        results.append({"title": title, "url": url, "snippet": snippet})
    return results


def search_public_web(
    query: str,
    *,
    max_results: int = DEFAULT_MAX_RESULTS,
    search_fn: Callable[[str, int], list[dict[str, Any]]] | None = None,
) -> list[dict[str, str]]:
    """
    Search the public web and return title, URL, and snippet rows.

    Uses the ``ddgs`` metasearch package (no API key). The default path
    retries transient provider failures on alternate backends. Results may
    mention login-gated sites; Jarvis must not fetch those pages.

    An empty list means the provider returned no hits. Provider exceptions
    raise ``WebSearchError`` instead of looking like an empty result.

    Args:
        query: Search query string.
        max_results: Desired result count (clamped to 1..10).
        search_fn: Optional injectable search callable for tests. Receives
            ``(query, max_results)`` and returns raw result dicts. When set,
            retries are skipped and exceptions propagate unchanged.

    Returns:
        List of ``{"title", "url", "snippet"}`` dictionaries. May be empty.

    Raises:
        ValueError: If ``query`` is empty after stripping.
        WebSearchError: If the default ``ddgs`` path fails.
    """
    cleaned = (query or "").strip()
    if not cleaned:
        raise ValueError("Search query is empty.")
    limit = _clamp_max_results(max_results)
    if search_fn is None:
        raw = _search_ddgs(cleaned, limit)
    else:
        raw = search_fn(cleaned, limit)
    return _normalize_hits(raw)


def _clamp_image_results(max_results: int) -> int:
    """Clamp image hit count to ``1..HARD_MAX_IMAGE_RESULTS``."""
    if max_results < 1:
        return 1
    if max_results > HARD_MAX_IMAGE_RESULTS:
        return HARD_MAX_IMAGE_RESULTS
    return max_results


def _is_direct_image_url(url: str) -> bool:
    """Return whether ``url`` is an http(s) link to a common image file."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    return parsed.path.lower().endswith(_IMAGE_EXTENSIONS)


def _prefer_stable_image_hosts(
    results: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Keep input order, but move Wikimedia-style hosts ahead of the rest."""

    def sort_key(index_item: tuple[int, dict[str, str]]) -> tuple[int, int]:
        index, item = index_item
        host = urlparse(item["image_url"]).netloc.lower()
        preferred = any(marker in host for marker in _PREFERRED_IMAGE_HOSTS)
        return (0 if preferred else 1, index)

    return [item for _, item in sorted(enumerate(results), key=sort_key)]


def _normalize_image_hits(raw: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Map provider rows to direct image URLs, dropping page-only hits."""
    results: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw:
        image_url = str(item.get("image") or "").strip()
        if not _is_direct_image_url(image_url) or image_url in seen:
            continue
        seen.add(image_url)
        results.append(
            {
                "title": str(item.get("title") or "").strip(),
                "image_url": image_url,
                "page_url": str(item.get("url") or item.get("href") or "").strip(),
                "source": str(item.get("source") or "").strip(),
            }
        )
    return _prefer_stable_image_hosts(results)


def search_public_images(
    query: str,
    *,
    max_results: int = DEFAULT_IMAGE_RESULTS,
    search_fn: Callable[[str, int], list[dict[str, Any]]] | None = None,
) -> list[dict[str, str]]:
    """
    Search public images and return direct image URL candidates.

    This is the MVP path for inline chat images: a few direct URLs, with
    Wikimedia-style hosts preferred when they appear. It is not a ranked
    retrieval pipeline.

    Args:
        query: Image search query.
        max_results: Desired candidate count (clamped to 1..3).
        search_fn: Optional injectable search callable for tests. Receives
            ``(query, max_results)`` and returns raw ``ddgs`` image rows.

    Returns:
        List of ``{"title", "image_url", "page_url", "source"}``. May be empty.

    Raises:
        ValueError: If ``query`` is empty after stripping.
        WebSearchError: If the default ``ddgs`` path fails.
    """
    cleaned = (query or "").strip()
    if not cleaned:
        raise ValueError("Search query is empty.")
    limit = _clamp_image_results(max_results)
    if search_fn is None:
        raw = _search_ddgs_images(cleaned, limit)
    else:
        raw = search_fn(cleaned, limit)
    return _normalize_image_hits(raw)[:limit]
