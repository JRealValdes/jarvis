"""URL policy for public-page fetching: schemes, blocked hosts, robots.txt."""

from __future__ import annotations

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

# Jarvis identifies itself politely when checking robots.txt and fetching pages.
USER_AGENT = "JarvisBot/0.1 (+https://github.com/JRealValdes/jarvis; public-read only)"

ALLOWED_SCHEMES = frozenset({"http", "https"})

# Login-gated / ToS-blocked targets. Match hostname suffix (e.g. www.glassdoor.com).
BLOCKED_HOST_SUFFIXES = (
    "glassdoor.com",
    "glassdoor.es",
    "glassdoor.co.uk",
    "glassdoor.ca",
    "glassdoor.de",
    "glassdoor.fr",
    "glassdoor.it",
    "glassdoor.nl",
    "glassdoor.ie",
    "glassdoor.com.au",
    "glassdoor.com.mx",
    "glassdoor.com.br",
    "glassdoor.co.in",
    "glassdoor.sg",
    "glassdoor.com.hk",
)

ROBOTS_TIMEOUT_SECONDS = 5.0


class UrlPolicyError(ValueError):
    """Raised when a URL must not be fetched under Jarvis public-web rules."""


def normalize_hostname(hostname: str | None) -> str:
    """
    Lowercase a hostname and strip a leading ``www.``.

    Args:
        hostname: Raw hostname from ``urlparse``, or None.

    Returns:
        Normalized hostname, or empty string when missing.
    """
    if not hostname:
        return ""
    host = hostname.strip().lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def is_blocked_host(hostname: str | None) -> bool:
    """
    Return True when the host is a disallowed login-gated target.

    Args:
        hostname: Hostname to check (with or without ``www.``).

    Returns:
        True if the host matches a blocked suffix (e.g. Glassdoor).
    """
    host = normalize_hostname(hostname)
    if not host:
        return False
    for suffix in BLOCKED_HOST_SUFFIXES:
        if host == suffix or host.endswith("." + suffix):
            return True
    return False


def assert_allowed_scheme(url: str) -> None:
    """
    Reject URLs that are not ``http`` or ``https``.

    Args:
        url: Absolute URL.

    Raises:
        UrlPolicyError: If the scheme is missing or not allowed.
    """
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        raise UrlPolicyError(
            f"Only http and https URLs are allowed (got scheme={scheme!r})."
        )


def assert_not_blocked(url: str) -> None:
    """
    Reject blocked hosts such as Glassdoor.

    Args:
        url: Absolute URL.

    Raises:
        UrlPolicyError: If the host is on the block list.
    """
    parsed = urlparse(url)
    if is_blocked_host(parsed.hostname):
        raise UrlPolicyError(
            "Refusing to fetch this host: login-gated job boards "
            "(including Glassdoor) are out of scope. Use a public page "
            "or rely on search snippets only."
        )


def robots_txt_allows(url: str, *, user_agent: str = USER_AGENT) -> bool:
    """
    Check whether ``robots.txt`` allows fetching ``url`` for ``user_agent``.

    When ``robots.txt`` cannot be read (network/parse errors), allow the
    fetch so public pages remain reachable; blocked hosts and schemes are
    enforced separately.

    Args:
        url: Absolute ``http``/``https`` URL to fetch.
        user_agent: User-Agent used for the robots check and later GET.

    Returns:
        False only when robots.txt is readable and disallows the path.
    """
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = RobotFileParser()
    try:
        response = requests.get(
            robots_url,
            timeout=ROBOTS_TIMEOUT_SECONDS,
            headers={"User-Agent": user_agent},
        )
        if response.status_code >= 400:
            return True
        parser.parse(response.text.splitlines())
    except requests.RequestException:
        return True
    return parser.can_fetch(user_agent, url)


def assert_fetchable_url(url: str, *, check_robots: bool = True) -> str:
    """
    Validate that ``url`` may be fetched under public-web rules.

    Args:
        url: Candidate absolute URL.
        check_robots: When True, honor ``robots.txt`` disallow rules.

    Returns:
        Stripped URL string.

    Raises:
        UrlPolicyError: If the URL is empty, uses a bad scheme, is blocked,
            or is disallowed by robots.txt.
    """
    cleaned = (url or "").strip()
    if not cleaned:
        raise UrlPolicyError("URL is empty.")
    assert_allowed_scheme(cleaned)
    assert_not_blocked(cleaned)
    if check_robots and not robots_txt_allows(cleaned):
        raise UrlPolicyError(
            f"robots.txt disallows fetching this URL for {USER_AGENT}."
        )
    return cleaned
