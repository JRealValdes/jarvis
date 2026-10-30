"""Admin-only tool that creates one image and stores it for the reply."""

from __future__ import annotations

import logging

from langchain_core.tools import tool

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
        "Generated image stored. Embed it once, in the middle of the reply, "
        "as ![short alt](Image URL). Copy the Image URL exactly. "
        "Do not invent or edit it.\n"
        f"Image URL: {url}"
    )


@tool(GENERATION_TOOL_NAME)
def generate_image_tool(prompt: str = "") -> str:
    """
    Create a new image for an admin and return a URL to embed.

    Call once when the user asks you to draw, create, or generate a picture.
    Do not call it to find a real artwork, place, or photo that already
    exists; use web_image_search_tool for those. Non-admins cannot use this
    tool. Embed the returned Image URL exactly as ![alt](Image URL). Never
    invent a URL.

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
            "Image generation failed. Reply with text only. "
            "Do not invent an image URL."
        )
    if stored is None:
        return (
            "The image could not be stored. Reply with text only. "
            "Do not invent an image URL."
        )
    return _format_stored(stored.public_url)
