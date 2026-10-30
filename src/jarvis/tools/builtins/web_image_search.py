"""LangChain tool that finds direct public image URLs for inline replies."""

from __future__ import annotations

import logging

from langchain_core.tools import tool

from jarvis.infrastructure.images.attribution import format_image_attribution
from jarvis.infrastructure.images.vision_verify import (
    image_matches_subject,
    reserve_vision_check,
)
from jarvis.infrastructure.web.search import (
    DEFAULT_IMAGE_RESULTS,
    MAX_INLINE_IMAGES_PER_REPLY,
    WebSearchError,
    search_public_images,
)

logger = logging.getLogger(__name__)

_EMBED_RULES = (
    f"Embed at most {MAX_INLINE_IMAGES_PER_REPLY} image in the reply, "
    "and only when a picture helps. Copy one Image URL below exactly into "
    "markdown as ![short alt](Image URL), in the middle of the explanation. "
    "On the next line, copy that same candidate's Attribution text exactly. "
    "Never invent, shorten, or edit a URL, a source, or a license. Do not "
    "use the source-page URL as the image. If the Attribution line says "
    "Source unknown, write that. If none of these fit, reply with text only."
)


def _format_image_candidates(results: list[dict[str, str]]) -> str:
    """Format image hits so the model can copy a URL or skip images."""
    if not results:
        return (
            "No image candidates. Reply with text only. "
            "Do not invent an image URL."
        )
    lines = ["## Image candidates", _EMBED_RULES]
    for index, item in enumerate(results, start=1):
        title = item.get("title") or "(no title)"
        lines.append(f"{index}. **{title}**")
        lines.append(f"   - Image URL: {item.get('image_url') or ''}")
        lines.append(
            "   - Attribution: "
            + format_image_attribution(
                title=item.get("title") or "",
                page_url=item.get("page_url") or "",
                source=item.get("source") or "",
                license_name=item.get("license") or "",
            )
        )
    return "\n".join(lines)


def _storage_enabled() -> bool:
    """Read the storage flag at call time so tests can patch config."""
    from jarvis.core.config import IMAGE_STORAGE

    return IMAGE_STORAGE


def _with_stored_copies(results: list[dict[str, str]]) -> list[dict[str, str]]:
    """
    Save web images locally and point candidates at the Jarvis URL.

    When storage is off, or a download fails, the original hotlink stays.
    """
    if not _storage_enabled() or not results:
        return results
    from jarvis.infrastructure.images.store import persist_web_image

    rewritten: list[dict[str, str]] = []
    for item in results:
        original = item.get("image_url") or ""
        saved = persist_web_image(original) if original else None
        if saved is None:
            rewritten.append(item)
            continue
        copied = dict(item)
        copied["image_url"] = saved.public_url
        rewritten.append(copied)
    return rewritten


def _vision_verify_enabled() -> bool:
    """Read the operator flag at call time so tests can patch config."""
    from jarvis.core.config import VISION_VERIFY_IMAGES

    return VISION_VERIFY_IMAGES


def _candidates_after_vision_check(
    query: str,
    results: list[dict[str, str]],
) -> list[dict[str, str]] | None:
    """
    Keep only the best candidate when one vision check accepts it.

    Returns:
        The candidate list to show. ``None`` when the turn's single check
        was already spent and no further image may be offered.
    """
    if not _vision_verify_enabled() or not results:
        return results
    if not reserve_vision_check():
        return None
    best = results[0]
    if image_matches_subject(query, best.get("image_url") or ""):
        return [best]
    return []


@tool
def web_image_search_tool(
    query: str = "",
    max_results: int = DEFAULT_IMAGE_RESULTS,
) -> str:
    """
    Find public images that can be shown inline in a chat reply.

    Call once when a picture would help the user understand a specific
    artwork, place, object, person, or diagram. Do not call it for ordinary
    factual questions that text answers well.

    The result lists image URLs and one Attribution line each. Embed at
    most one image, copied exactly as ![alt](Image URL), and put that
    candidate's Attribution text on the next line. When image storage is
    on, the image URL points at Jarvis and the attribution still names the
    original page. Never invent a URL, a source, or a license. If there
    are no candidates, answer in text only.

    Parameters:
    - query: what the image should depict
    - max_results: how many candidates to return (default 3, max 3)
    """
    cleaned = (query or "").strip()
    if not cleaned:
        return (
            "Provide an image search query. Example: query='Van Gogh The Starry Night'. "
            "If you have no query, reply with text only and do not invent an image URL."
        )
    try:
        results = search_public_images(cleaned, max_results=max_results)
    except WebSearchError as exc:
        logger.warning("web_image_search_tool provider failure:\n%s", exc)
        return (
            f"{exc}\n\nReply with text only. Do not invent an image URL."
        )
    except Exception as exc:
        logger.warning("web_image_search_tool failed: %s", exc, exc_info=exc)
        return (
            "Image search failed. Reply with text only. "
            "Do not invent an image URL."
        )
    checked = _candidates_after_vision_check(cleaned, results)
    if checked is None:
        return (
            "Vision check already used this turn. Reply with text only. "
            "Do not invent an image URL."
        )
    return _format_image_candidates(_with_stored_copies(checked))
