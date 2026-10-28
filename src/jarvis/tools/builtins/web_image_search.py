"""LangChain tool that finds direct public image URLs for inline replies."""

from __future__ import annotations

import logging

from langchain_core.tools import tool

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
    "Never invent, shorten, or edit a URL. Do not use the source-page URL "
    "as the image. If none of these fit, reply with text only."
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
        page = item.get("page_url") or ""
        if page:
            lines.append(f"   - Source page: {page}")
        source = item.get("source") or ""
        if source:
            lines.append(f"   - Source: {source}")
    return "\n".join(lines)


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

    The result lists direct image URLs. Embed at most one, copied exactly
    as ![alt](Image URL). Never invent a URL. If there are no candidates,
    answer in text only.

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
    return _format_image_candidates(results)
