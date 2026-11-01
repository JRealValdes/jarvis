"""Admin-only image editing via the OpenAI Images Edit API.

Reference images for the current user turn are injected through a context
variable so the LangChain tool only needs a text prompt. One successful
generate or edit reservation is allowed per turn (shared budget).
"""

from __future__ import annotations

import base64
import logging
from contextvars import ContextVar
from datetime import datetime
from typing import Any

import openai

from jarvis.infrastructure.images.generate import (
    EDIT_TOOL_NAME,
    MAX_PROMPT_CHARS,
    ImageGenerationError,
    decode_images_api_b64,
    generation_allowed,
    map_images_api_bad_request,
    reserve_generation,
)
from jarvis.infrastructure.images.store import (
    GENERATED_KIND,
    StoredImage,
    store_image_bytes,
)

logger = logging.getLogger(__name__)

# Re-export for callers that import the tool name from this module.
__all__ = [
    "EDIT_TOOL_NAME",
    "EditReferenceImage",
    "clear_edit_reference_images",
    "edit_image_bytes",
    "edit_mask_image",
    "edit_reference_images",
    "edit_stored_image",
    "set_edit_reference_images",
]

_TEXT_ONLY_NO_URL = "Reply with text only. Do not invent an image URL."

_PROVIDER_FAILURE_MESSAGE = (
    "Image editing failed due to a provider or network error. Tell the "
    f"user they can retry shortly. {_TEXT_ONLY_NO_URL}"
)

_MEDIA_EXTENSIONS: dict[str, str] = {
    "image/gif": "gif",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


class EditReferenceImage:
    """One decoded attachment ready for the Images Edit API."""

    __slots__ = ("media_type", "data")

    def __init__(self, media_type: str, data: bytes) -> None:
        self.media_type = media_type
        self.data = data


_reference_images: ContextVar[tuple[EditReferenceImage, ...] | None] = ContextVar(
    "jarvis_image_edit_references", default=None
)
_edit_mask: ContextVar[EditReferenceImage | None] = ContextVar(
    "jarvis_image_edit_mask", default=None
)


def _decode_attachment(item: dict[str, str]) -> EditReferenceImage | None:
    """
    Decode one normalized attachment dict into bytes.

    Args:
        item: ``media_type`` + ``data_base64`` (already validated upstream).

    Returns:
        Decoded image, or None when the payload is empty or invalid.
    """
    media = str(item.get("media_type") or "").split(";")[0].strip().lower()
    if media == "image/jpg":
        media = "image/jpeg"
    raw = str(item.get("data_base64") or "").strip()
    if not media or not raw:
        return None
    compact = "".join(raw.split())
    if compact.startswith("data:") and "," in compact:
        compact = compact.split(",", 1)[1]
    try:
        data = base64.b64decode(compact, validate=True)
    except Exception:
        return None
    if not data:
        return None
    return EditReferenceImage(media, data)


def set_edit_reference_images(
    images: list[dict[str, str]] | None,
    *,
    mask: dict[str, str] | None = None,
) -> None:
    """
    Bind this turn's attached images (and optional mask) for edit_image_tool.

    Args:
        images: Normalized attachments from ``/ask`` (may be empty).
        mask: Optional mask attachment for a later phase; unused in UI yet.
    """
    decoded: list[EditReferenceImage] = []
    for item in images or []:
        ref = _decode_attachment(item)
        if ref is not None:
            decoded.append(ref)
    _reference_images.set(tuple(decoded))
    mask_ref = _decode_attachment(mask) if mask else None
    _edit_mask.set(mask_ref)


def clear_edit_reference_images() -> None:
    """Clear edit reference images and mask after the model turn."""
    _reference_images.set(None)
    _edit_mask.set(None)


def edit_reference_images() -> tuple[EditReferenceImage, ...]:
    """Return the reference images bound for the current turn."""
    return _reference_images.get() or ()


def edit_mask_image() -> EditReferenceImage | None:
    """Return the optional mask bound for the current turn."""
    return _edit_mask.get()


def _as_openai_file(
    ref: EditReferenceImage, *, index: int, prefix: str
) -> tuple[str, bytes, str]:
    """
    Build a multipart file tuple for the OpenAI SDK.

    Args:
        ref: Decoded image.
        index: Zero-based index for a stable filename.
        prefix: Filename prefix (``image`` or ``mask``).

    Returns:
        ``(filename, bytes, content_type)`` for ``images.edit``.
    """
    ext = _MEDIA_EXTENSIONS.get(ref.media_type, "png")
    return (f"{prefix}_{index}.{ext}", ref.data, ref.media_type)


def edit_image_bytes(
    prompt: str,
    images: list[EditReferenceImage] | tuple[EditReferenceImage, ...],
    *,
    mask: EditReferenceImage | None = None,
    client: Any | None = None,
) -> bytes:
    """
    Ask the Images Edit API to modify the reference image(s).

    Args:
        prompt: What to change while preserving the rest.
        images: One or more reference images (photo A, photo B, …).
        mask: Optional mask; editable region only (phase 2).
        client: Optional OpenAI client (tests).

    Returns:
        Edited image bytes.

    Raises:
        ImageGenerationError: If the provider refuses or returns nothing usable.
        ValueError: If ``prompt`` is empty/too long or ``images`` is empty.
    """
    cleaned = (prompt or "").strip()
    if not cleaned:
        raise ValueError("Prompt is empty.")
    if len(cleaned) > MAX_PROMPT_CHARS:
        raise ValueError(f"Prompt exceeds {MAX_PROMPT_CHARS} characters.")
    refs = list(images)
    if not refs:
        raise ValueError("At least one reference image is required.")
    from jarvis.core.config import (
        IMAGE_GENERATION_MODEL,
        IMAGE_GENERATION_QUALITY,
        IMAGE_GENERATION_SIZE,
    )

    api = client or openai.OpenAI()
    files = [_as_openai_file(ref, index=i, prefix="image") for i, ref in enumerate(refs)]
    image_arg: Any = files[0] if len(files) == 1 else files
    kwargs: dict[str, Any] = {
        "model": IMAGE_GENERATION_MODEL,
        "image": image_arg,
        "prompt": cleaned,
        "size": IMAGE_GENERATION_SIZE,
        "quality": IMAGE_GENERATION_QUALITY,
        "output_format": "png",
        "n": 1,
    }
    if mask is not None:
        kwargs["mask"] = _as_openai_file(mask, index=0, prefix="mask")
    try:
        response = api.images.edit(**kwargs)
    except openai.BadRequestError as exc:
        raise map_images_api_bad_request(exc) from exc
    except openai.OpenAIError as exc:
        logger.warning("Image editing failed: %s", exc)
        raise ImageGenerationError(_PROVIDER_FAILURE_MESSAGE) from exc
    return decode_images_api_b64(
        response,
        empty_message=(
            f"Image editing returned no image. {_TEXT_ONLY_NO_URL}"
        ),
        unreadable_message=(
            f"Image editing returned unreadable data. {_TEXT_ONLY_NO_URL}"
        ),
        empty_bytes_message=(
            f"Image editing returned an empty image. {_TEXT_ONLY_NO_URL}"
        ),
    )


def edit_stored_image(
    prompt: str,
    images: list[EditReferenceImage] | tuple[EditReferenceImage, ...] | None = None,
    *,
    mask: EditReferenceImage | None = None,
    client: Any | None = None,
    now: datetime | None = None,
) -> StoredImage | None:
    """
    Edit reference image(s) and save the result with the generated-image TTL.

    Args:
        prompt: What to change while preserving the rest.
        images: Reference images; defaults to the turn's bound attachments.
        mask: Optional mask; defaults to the turn's bound mask when omitted.
        client: Optional OpenAI client (tests).
        now: Clock override for tests.

    Returns:
        The stored record, or None when the bytes cannot be kept.

    Raises:
        ImageGenerationError: If editing fails.
        ValueError: If ``prompt`` is empty/too long or no images are available.
    """
    refs = tuple(images) if images is not None else edit_reference_images()
    mask_ref = mask if mask is not None else edit_mask_image()
    data = edit_image_bytes(prompt, refs, mask=mask_ref, client=client)
    return store_image_bytes(data, kind=GENERATED_KIND, source_url=None, now=now)
