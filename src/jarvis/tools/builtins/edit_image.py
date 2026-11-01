"""Admin-only tool that edits this turn's attached images and stores the result."""

from __future__ import annotations

import logging

from langchain_core.tools import tool

from jarvis.infrastructure.images.attribution import EDITED_IMAGE_CAPTION
from jarvis.infrastructure.images.edit import (
    EDIT_TOOL_NAME,
    edit_reference_images,
    edit_stored_image,
)
from jarvis.infrastructure.images.generate import (
    ImageGenerationError,
    generation_allowed,
    reserve_generation,
)

logger = logging.getLogger(__name__)


def _format_stored(url: str) -> str:
    return (
        "Edited image stored. Paste the next two lines into the middle of "
        "your reply exactly as written. The path starts with /images/ — it is "
        "not a website hostname. Do not add https://, http://, or any host, "
        "and do not shorten the path.\n"
        f"![short alt]({url})\n"
        f"{EDITED_IMAGE_CAPTION}"
    )


@tool(EDIT_TOOL_NAME)
def edit_image_tool(prompt: str = "") -> str:
    """
    Edit this turn's attached photo(s) and return a URL to embed.

    Call once when the user attached one or more images and wants you to
    change, restyle, modernize, compose, or otherwise modify them while
    staying faithful to those photos (for example: redesign furniture in a
    room photo, open closed eyes, place a person from one photo into another).
    The attached images are already available to this tool—do not ask the
    user to resend them. Prefer this tool over generate_image_tool whenever
    the result should keep the attached photo as the base. Do not call it to
    invent a brand-new picture with no photo to preserve, or to find a real
    artwork online. Non-admins cannot use this tool. Paste the returned
    Markdown image line and caption exactly. Never invent a URL or turn
    /images/... into https://images/....

    Parameters:
    - prompt: what to change; say what must stay the same when it matters
    """
    if not generation_allowed():
        return (
            "Image editing is available to admins only. Reply with text "
            "only. Do not invent an image URL."
        )
    cleaned = (prompt or "").strip()
    if not cleaned:
        return (
            "Provide a description of the edit to apply. If you have no "
            "description, reply with text only and do not invent an image URL."
        )
    if not edit_reference_images():
        return (
            "No attached images are available on this turn for editing. Ask "
            "the user to attach the photo(s) and retry, or use "
            "generate_image_tool only if they want a brand-new picture from "
            "text. Reply with text only. Do not invent an image URL."
        )
    if not reserve_generation():
        return (
            "Image generation or editing already used this turn. Reply with "
            "text only. Do not invent an image URL."
        )
    try:
        stored = edit_stored_image(cleaned)
    except ImageGenerationError as exc:
        logger.warning("edit_image_tool failed: %s", exc)
        return exc.message
    except ValueError as exc:
        logger.warning("edit_image_tool rejected the prompt: %s", exc)
        return (
            f"{exc} Reply with text only. Do not invent an image URL."
        )
    except Exception as exc:
        logger.warning("edit_image_tool failed: %s", exc, exc_info=exc)
        return (
            "Image editing failed unexpectedly. Tell the user they can "
            "retry shortly. Reply with text only. Do not invent an image URL."
        )
    if stored is None:
        return (
            "The edited image could not be stored. Reply with text only. "
            "Do not invent an image URL."
        )
    return _format_stored(stored.public_url)
