"""Admin-only tool that creates one image and stores it for the reply."""

from __future__ import annotations

import logging

from langchain_core.tools import tool

from jarvis.infrastructure.images.attribution import GENERATED_IMAGE_CAPTION
from jarvis.infrastructure.images.generate import (
    GENERATION_TOOL_NAME,
    ImageGenerationError,
    generate_stored_image,
    generation_allowed,
    reserve_generation,
)

logger = logging.getLogger(__name__)


def _format_stored(url: str) -> str:
    return (
        "Generated image stored. Paste the next two lines into the middle of "
        "your reply exactly as written. The path starts with /images/ — it is "
        "not a website hostname. Do not add https://, http://, or any host, "
        "and do not shorten the path.\n"
        f"![short alt]({url})\n"
        f"{GENERATED_IMAGE_CAPTION}"
    )


@tool(GENERATION_TOOL_NAME)
def generate_image_tool(prompt: str = "") -> str:
    """
    Create a new image for an admin and return a URL to embed.

    Call once when the user asks you to draw, create, or generate a brand-new
    picture from text with no attached photo that must be preserved. When the
    user attached image(s) and wants those photos edited or composed, use
    edit_image_tool instead. Do not call it to find a real artwork, place, or
    photo that already exists; use web_image_search_tool for those. Non-admins
    cannot use this tool. Paste the returned Markdown image line and caption
    exactly. Never invent a URL or turn /images/... into https://images/....

    Parameters:
    - prompt: what the new image should show
    """
    if not generation_allowed():
        return (
            "Image generation is available to admins only. Reply with text "
            "only. Do not invent an image URL."
        )
    cleaned = (prompt or "").strip()
    if not cleaned:
        return (
            "Provide a description of the image to create. If you have no "
            "description, reply with text only and do not invent an image URL."
        )
    if not reserve_generation():
        return (
            "Image generation already used this turn. Reply with text only. "
            "Do not invent an image URL."
        )
    try:
        stored = generate_stored_image(cleaned)
    except ImageGenerationError as exc:
        logger.warning("generate_image_tool failed: %s", exc)
        return exc.message
    except ValueError as exc:
        logger.warning("generate_image_tool rejected the prompt: %s", exc)
        return (
            f"{exc} Reply with text only. Do not invent an image URL."
        )
    except Exception as exc:
        logger.warning("generate_image_tool failed: %s", exc, exc_info=exc)
        return (
            "Image generation failed unexpectedly. Tell the user they can "
            "retry shortly. Reply with text only. Do not invent an image URL."
        )
    if stored is None:
        return (
            "The image could not be stored. Reply with text only. "
            "Do not invent an image URL."
        )
    return _format_stored(stored.public_url)
