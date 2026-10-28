"""Validate image attachments and shape multimodal human messages."""

from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage

MAX_IMAGES_PER_TURN: int = 4
MAX_IMAGE_BYTES: int = 4 * 1024 * 1024
IMAGE_ONLY_PROMPT: str = "Please look at the attached image(s)."
HISTORY_IMAGE_MARKER: str = "[Image attached]"
OMITTED_IMAGE_NOTE: str = (
    "[Image attached on an earlier message; omitted from this model call "
    "to limit context.]"
)

SUPPORTED_IMAGE_MEDIA_TYPES: frozenset[str] = frozenset(
    {
        "image/gif",
        "image/jpeg",
        "image/png",
        "image/webp",
    }
)

_EXTENSION_MEDIA_TYPES: dict[str, str] = {
    ".gif": "image/gif",
    ".jpeg": "image/jpeg",
    ".jpg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

_DATA_URL = re.compile(
    r"^data:(?P<media>[\w/+.-]+);base64,(?P<data>[A-Za-z0-9+/=\s]+)$",
    re.DOTALL,
)


class ImageAttachmentError(Exception):
    """Raised when a client image cannot be accepted."""

    def __init__(self, message: str, *, code: str = "invalid_image") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class VisionNotSupportedError(Exception):
    """Raised when the selected chat model cannot view images."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _field(item: Any, name: str) -> str:
    if isinstance(item, dict):
        value = item.get(name, "")
    else:
        value = getattr(item, name, "")
    return "" if value is None else str(value)


def _canonical_media_type(media_type: str) -> str:
    media = media_type.split(";")[0].strip().lower()
    if media == "image/jpg":
        return "image/jpeg"
    return media


def _decode_base64_payload(raw: str) -> tuple[str, str]:
    """
    Return ``(media_type_or_empty, canonical_base64)`` from a payload.

    A ``data:`` URL may override the declared media type.

    Args:
        raw: Base64 text or a data URL.

    Returns:
        Media type from the data URL (possibly empty) and canonical base64.

    Raises:
        ImageAttachmentError: If the payload is not valid base64.
    """
    text = raw.strip()
    media = ""
    match = _DATA_URL.match(text)
    if match:
        media = _canonical_media_type(match.group("media"))
        text = match.group("data")
    compact = "".join(text.split())
    try:
        decoded = base64.b64decode(compact, validate=True)
    except Exception as exc:
        raise ImageAttachmentError(
            "Image data is not valid base64.",
            code="invalid_base64",
        ) from exc
    if not decoded:
        raise ImageAttachmentError("Image file is empty.", code="empty_image")
    if len(decoded) > MAX_IMAGE_BYTES:
        raise ImageAttachmentError(
            f"Image exceeds max size of {MAX_IMAGE_BYTES} bytes.",
            code="image_too_large",
        )
    return media, compact


def normalize_image_attachments(images: list[Any] | None) -> list[dict[str, str]]:
    """
    Validate and normalize image attachments for one user turn.

    Args:
        images: Dicts or objects with ``media_type`` and ``data_base64``.

    Returns:
        List of ``{media_type, data_base64}`` ready for a data URL.

    Raises:
        ImageAttachmentError: On count, type, or payload errors.
    """
    items = list(images or [])
    if len(items) > MAX_IMAGES_PER_TURN:
        raise ImageAttachmentError(
            f"At most {MAX_IMAGES_PER_TURN} images are allowed per message.",
            code="too_many_images",
        )
    normalized: list[dict[str, str]] = []
    for item in items:
        declared = _canonical_media_type(_field(item, "media_type"))
        embedded_media, payload = _decode_base64_payload(_field(item, "data_base64"))
        media = embedded_media or declared
        if media not in SUPPORTED_IMAGE_MEDIA_TYPES:
            allowed = ", ".join(sorted(SUPPORTED_IMAGE_MEDIA_TYPES))
            raise ImageAttachmentError(
                f"Unsupported image type '{media or '(none)'}'. Allowed: {allowed}.",
                code="unsupported_image_type",
            )
        normalized.append({"media_type": media, "data_base64": payload})
    return normalized


def images_from_file_paths(paths: list[str] | str | None) -> list[dict[str, str]]:
    """
    Read local image files into normalized attachment dicts.

    Args:
        paths: One path, a list of paths, or None.

    Returns:
        Normalized attachments.

    Raises:
        ImageAttachmentError: If a path is missing or the type/size is invalid.
    """
    if not paths:
        return []
    if isinstance(paths, str):
        paths = [paths]
    raw_items: list[dict[str, str]] = []
    for path in paths:
        file_path = Path(path)
        if not file_path.is_file():
            raise ImageAttachmentError(
                f"Image file does not exist: {file_path}",
                code="file_not_found",
            )
        media = _EXTENSION_MEDIA_TYPES.get(file_path.suffix.lower(), "")
        if not media:
            raise ImageAttachmentError(
                f"Unsupported image file extension '{file_path.suffix}'.",
                code="unsupported_image_type",
            )
        encoded = base64.b64encode(file_path.read_bytes()).decode("ascii")
        raw_items.append({"media_type": media, "data_base64": encoded})
    return normalize_image_attachments(raw_items)


def build_human_message(
    prompt: str,
    images: list[dict[str, str]] | None = None,
) -> HumanMessage:
    """
    Build a human message, with image blocks when attachments are present.

    Args:
        prompt: User text. Blank text with images uses ``IMAGE_ONLY_PROMPT``.
        images: Normalized ``{media_type, data_base64}`` dicts.

    Returns:
        A string ``HumanMessage`` when there are no images, otherwise a
        multimodal content list (text block, then one image block each).
    """
    attachments = list(images or [])
    text = prompt.strip()
    if not attachments:
        return HumanMessage(content=text)
    if not text:
        text = IMAGE_ONLY_PROMPT
    blocks: list[dict[str, Any]] = [{"type": "text", "text": text}]
    for image in attachments:
        blocks.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{image['media_type']};base64,{image['data_base64']}",
                },
            }
        )
    return HumanMessage(content=blocks)


def _image_blocks(content: Any) -> list[dict[str, Any]]:
    if not isinstance(content, list):
        return []
    return [
        block
        for block in content
        if isinstance(block, dict) and block.get("type") == "image_url"
    ]


def human_content_for_history(content: Any) -> str:
    """
    Render human message content for ``/message-history`` without image bytes.

    Args:
        content: LangChain human ``content`` (string or content blocks).

    Returns:
        Plain text. Each image becomes ``[Image attached]``.
    """
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            if block.strip():
                parts.append(block)
            continue
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            text = str(block.get("text") or "").strip()
            if text:
                parts.append(text)
        elif block.get("type") == "image_url":
            parts.append(HISTORY_IMAGE_MARKER)
    return "\n".join(parts)


def _without_images(content: Any) -> str:
    text = human_content_for_history(content)
    lines = [
        line
        for line in text.split("\n")
        if line != HISTORY_IMAGE_MARKER and line.strip()
    ]
    if lines:
        return "\n".join([*lines, OMITTED_IMAGE_NOTE])
    return OMITTED_IMAGE_NOTE


def prepare_messages_for_model(messages: list) -> list:
    """
    Keep image bytes only on the latest human message that has them.

    Older image turns stay in the checkpoint, but the model call replaces
    their pixels with a short note so follow-ups can still see the latest
    attachment without resending every prior image.

    Args:
        messages: Checkpoint messages about to be sent to the chat model.

    Returns:
        A list safe to pass to the model. Unchanged when no images are present.
    """
    last_with_images: int | None = None
    for index, message in enumerate(messages):
        if isinstance(message, HumanMessage) and _image_blocks(message.content):
            last_with_images = index
    if last_with_images is None:
        return messages
    prepared: list = []
    for index, message in enumerate(messages):
        if (
            index != last_with_images
            and isinstance(message, HumanMessage)
            and _image_blocks(message.content)
        ):
            prepared.append(
                message.model_copy(
                    update={"content": _without_images(message.content)}
                )
            )
        else:
            prepared.append(message)
    return prepared
