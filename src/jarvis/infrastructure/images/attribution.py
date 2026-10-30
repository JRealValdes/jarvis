"""Caption text shown under a chat image. Licenses are never invented."""

from __future__ import annotations

from urllib.parse import urlparse

SOURCE_UNKNOWN = "Source unknown"
GENERATED_IMAGE_CAPTION = "Generated image"


def _plain(value: str) -> str:
    """Collapse whitespace and brackets so a caption cannot break markdown."""
    cleaned = " ".join((value or "").split())
    return cleaned.replace("[", "(").replace("]", ")")


def _http_url(value: str) -> str:
    """Return ``value`` when it is an http(s) URL, otherwise an empty string."""
    cleaned = (value or "").strip()
    parsed = urlparse(cleaned)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return cleaned
    return ""


def format_image_attribution(
    *,
    title: str = "",
    page_url: str = "",
    source: str = "",
    license_name: str = "",
) -> str:
    """
    Build one caption line from fields the image tool actually returned.

    Args:
        title: Provider title. Omitted when empty.
        page_url: Page to link. Used only when it is http(s).
        source: Site name. Becomes the link text, or plain text when there
            is no page URL.
        license_name: License hint from the provider. Omitted when empty.
            This function never fills one in.

    Returns:
        A single markdown line. ``Source unknown`` when every field is empty.
    """
    title_text = _plain(title)
    source_text = _plain(source)
    license_text = _plain(license_name)
    link = _http_url(page_url)
    parts: list[str] = []
    if title_text:
        parts.append(title_text)
    if link:
        parts.append(f"[{source_text or 'Source'}]({link})")
    elif source_text:
        parts.append(source_text)
    caption = " · ".join(parts)
    if license_text:
        hint = f"License: {license_text}"
        caption = f"{caption} · {hint}" if caption else hint
    return caption or SOURCE_UNKNOWN
