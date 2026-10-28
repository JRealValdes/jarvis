"""Score image-search hits when ranked retrieval is enabled.

The MVP path only prefers Wikimedia hosts. This module adds title overlap,
a minimum pixel size, and the same host preference, then returns the best
candidates. It is not a commercial image-search ranker.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

PREFERRED_IMAGE_HOSTS: tuple[str, ...] = (
    "commons.wikimedia.org",
    "upload.wikimedia.org",
    "wikipedia.org",
)
MIN_IMAGE_EDGE_PX: int = 200
_TOKEN = re.compile(r"[a-z0-9]+")
_TITLE_WEIGHT = 50.0
_PREFERRED_HOST_BONUS = 25.0
_ADEQUATE_SIZE_BONUS = 15.0


def _tokens(text: str) -> set[str]:
    """Return lowercase tokens longer than two characters."""
    return {token for token in _TOKEN.findall(text.lower()) if len(token) > 2}


def _edge_px(value: str) -> int | None:
    """Parse a pixel edge such as ``800`` or ``800px``. Unknown values stay None."""
    text = (value or "").strip().lower().removesuffix("px").strip()
    if not text.isdigit():
        return None
    return int(text)


def _preferred_host(image_url: str) -> bool:
    host = urlparse(image_url).netloc.lower()
    return any(marker in host for marker in PREFERRED_IMAGE_HOSTS)


def _title_score(query: str, title: str) -> float:
    query_tokens = _tokens(query)
    if not query_tokens:
        return 0.0
    overlap = len(query_tokens & _tokens(title)) / len(query_tokens)
    return overlap * _TITLE_WEIGHT


def rank_image_candidates(
    query: str,
    candidates: list[dict[str, str]],
) -> list[dict[str, str]]:
    """
    Filter and sort image candidates for the ranked-retrieval path.

    Drops hits whose width and height are both known and either edge is
    below ``MIN_IMAGE_EDGE_PX``. Missing dimensions are kept. Higher scores
    come first; equal scores keep the original order.

    Args:
        query: The image search query.
        candidates: Normalized rows with ``title``, ``image_url``, and
            optional ``width`` / ``height``.

    Returns:
        The same row dicts, best first. May be empty.
    """
    scored: list[tuple[float, int, dict[str, str]]] = []
    for index, item in enumerate(candidates):
        width = _edge_px(item.get("width", ""))
        height = _edge_px(item.get("height", ""))
        if (
            width is not None
            and height is not None
            and (width < MIN_IMAGE_EDGE_PX or height < MIN_IMAGE_EDGE_PX)
        ):
            continue
        score = _title_score(query, item.get("title", ""))
        if _preferred_host(item.get("image_url", "")):
            score += _PREFERRED_HOST_BONUS
        if (
            width is not None
            and height is not None
            and width >= MIN_IMAGE_EDGE_PX
            and height >= MIN_IMAGE_EDGE_PX
        ):
            score += _ADEQUATE_SIZE_BONUS
        scored.append((score, index, item))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [item for _, _, item in scored]
