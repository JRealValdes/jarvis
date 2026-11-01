"""Admin-only image generation via the OpenAI Images API.

The tool is hidden from non-admins at bind time. The generator also refuses
the call, so a cached graph cannot spend the API on someone who is not an
admin. One successful reservation is allowed per user turn.
"""

from __future__ import annotations

import base64
import logging
from contextvars import ContextVar
from datetime import datetime
from typing import Any

import openai

from jarvis.infrastructure.images.store import (
    GENERATED_KIND,
    StoredImage,
    store_image_bytes,
)

logger = logging.getLogger(__name__)

GENERATION_TOOL_NAME = "generate_image_tool"
# Keep in sync with ``edit.EDIT_TOOL_NAME`` (string literal avoids a cycle).
EDIT_TOOL_NAME = "edit_image_tool"
ADMIN_IMAGE_TOOL_NAMES: frozenset[str] = frozenset(
    {GENERATION_TOOL_NAME, EDIT_TOOL_NAME}
)
MAX_GENERATIONS_PER_TURN = 1
MAX_PROMPT_CHARS = 4_000


class _GenerationBudget:
    """Mutable counter shared across LangChain's copied tool context."""

    def __init__(self) -> None:
        self.used = 0


_allowed: ContextVar[bool] = ContextVar("jarvis_image_generation_admin", default=False)
_budget: ContextVar[_GenerationBudget | None] = ContextVar(
    "jarvis_image_generation_budget", default=None
)


class ImageGenerationError(Exception):
    """The Images API refused the prompt or could not return bytes."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


# OpenAI Images API codes that mean the prompt was blocked by safety/policy.
_POLICY_REFUSAL_CODES = frozenset(
    {
        "content_policy_violation",
        "moderation_blocked",
    }
)

_TEXT_ONLY_NO_URL = "Reply with text only. Do not invent an image URL."

_POLICY_REFUSAL_MESSAGE = (
    "Image generation was blocked by the image provider's safety/content "
    "policy. Explain briefly that this picture cannot be created under those "
    "rules and suggest rephrasing the request. "
    f"{_TEXT_ONLY_NO_URL}"
)

_GENERIC_REFUSAL_MESSAGE = (
    "Image generation was refused by the provider (invalid or disallowed "
    f"request). Explain briefly and suggest adjusting the description. "
    f"{_TEXT_ONLY_NO_URL}"
)

_PROVIDER_FAILURE_MESSAGE = (
    "Image generation failed due to a provider or network error. Tell the "
    f"user they can retry shortly. {_TEXT_ONLY_NO_URL}"
)


def _provider_error_code(exc: BaseException) -> str | None:
    """
    Extract a provider error code from an OpenAI exception when present.

    Args:
        exc: Exception raised by the Images API client.

    Returns:
        Code string, or None when unavailable.
    """
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code.strip():
        return code.strip()
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        nested = body.get("code")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
        error = body.get("error")
        if isinstance(error, dict):
            nested = error.get("code")
            if isinstance(nested, str) and nested.strip():
                return nested.strip()
    return None


def _is_policy_refusal(exc: openai.BadRequestError) -> bool:
    """
    Return True when the Images API refused the prompt for safety/policy.

    Args:
        exc: ``BadRequestError`` from ``images.generate``.

    Returns:
        True for known policy codes or clear safety/policy wording.
    """
    code = _provider_error_code(exc)
    if code in _POLICY_REFUSAL_CODES:
        return True
    haystack = " ".join(
        part
        for part in (
            code or "",
            str(getattr(exc, "message", "") or ""),
            str(exc),
            str(getattr(exc, "body", "") or ""),
        )
        if part
    ).lower()
    return (
        "content_policy" in haystack
        or "content policy" in haystack
        or "safety system" in haystack
        or "safety policies" in haystack
    )


def set_generation_allowed(allowed: bool) -> None:
    """
    Record whether the user turn that is about to run may generate images.

    Args:
        allowed: True only for an authenticated admin.
    """
    _allowed.set(bool(allowed))


def generation_allowed() -> bool:
    """Return True when the current turn belongs to an admin."""
    return _allowed.get()


def reset_generation_budget() -> None:
    """Allow one image generation for the user turn that is about to run."""
    _budget.set(_GenerationBudget())


def reserve_generation() -> bool:
    """
    Reserve the single generation for this turn.

    Returns:
        True when this call may contact the Images API.
    """
    budget = _budget.get()
    if budget is None:
        budget = _GenerationBudget()
        _budget.set(budget)
    if budget.used >= MAX_GENERATIONS_PER_TURN:
        return False
    budget.used += 1
    return True


def visible_tools(tools: list[Any]) -> list[Any]:
    """
    Drop admin image tools unless the current turn is an admin.

    Args:
        tools: Tools that would otherwise be bound to the model.

    Returns:
        The same list, without generate/edit image tools for non-admins.
    """
    if generation_allowed():
        return list(tools)
    return [
        tool
        for tool in tools
        if getattr(tool, "name", None) not in ADMIN_IMAGE_TOOL_NAMES
    ]


def generate_image_bytes(prompt: str, *, client: Any | None = None) -> bytes:
    """
    Ask the Images API for one PNG and return the decoded bytes.

    Args:
        prompt: What the image should show.
        client: Optional OpenAI client (tests).

    Returns:
        PNG (or other supported image) bytes.

    Raises:
        ImageGenerationError: If the provider refuses or returns nothing usable.
        ValueError: If ``prompt`` is empty or too long.
    """
    cleaned = (prompt or "").strip()
    if not cleaned:
        raise ValueError("Prompt is empty.")
    if len(cleaned) > MAX_PROMPT_CHARS:
        raise ValueError(f"Prompt exceeds {MAX_PROMPT_CHARS} characters.")
    from jarvis.core.config import (
        IMAGE_GENERATION_MODEL,
        IMAGE_GENERATION_QUALITY,
        IMAGE_GENERATION_SIZE,
    )

    api = client or openai.OpenAI()
    try:
        response = api.images.generate(
            model=IMAGE_GENERATION_MODEL,
            prompt=cleaned,
            size=IMAGE_GENERATION_SIZE,
            quality=IMAGE_GENERATION_QUALITY,
            output_format="png",
            n=1,
        )
    except openai.BadRequestError as exc:
        raise map_images_api_bad_request(exc) from exc
    except openai.OpenAIError as exc:
        logger.warning("Image generation failed: %s", exc)
        raise ImageGenerationError(_PROVIDER_FAILURE_MESSAGE) from exc
    return decode_images_api_b64(
        response,
        empty_message=(
            f"Image generation returned no image. {_TEXT_ONLY_NO_URL}"
        ),
        unreadable_message=(
            f"Image generation returned unreadable data. {_TEXT_ONLY_NO_URL}"
        ),
        empty_bytes_message=(
            f"Image generation returned an empty image. {_TEXT_ONLY_NO_URL}"
        ),
    )


def generate_stored_image(
    prompt: str,
    *,
    client: Any | None = None,
    now: datetime | None = None,
) -> StoredImage | None:
    """
    Generate one image and save it with the generated-image TTL.

    Args:
        prompt: What the image should show.
        client: Optional OpenAI client (tests).
        now: Clock override for tests.

    Returns:
        The stored record, or None when the bytes cannot be kept.

    Raises:
        ImageGenerationError: If generation fails.
        ValueError: If ``prompt`` is empty or too long.
    """
    data = generate_image_bytes(prompt, client=client)
    return store_image_bytes(data, kind=GENERATED_KIND, source_url=None, now=now)


def first_images_api_b64(response: Any) -> str:
    """
    Return the first ``b64_json`` payload from an Images API response.

    Args:
        response: ``ImagesResponse`` (or test double) from generate/edit.

    Returns:
        Base64 text, or empty when missing.
    """
    items = getattr(response, "data", None) or []
    if not items:
        return ""
    raw = getattr(items[0], "b64_json", None) or ""
    text = str(raw).strip()
    if text.startswith("data:") and "," in text:
        text = text.split(",", 1)[1]
    return text


def decode_images_api_b64(
    response: Any,
    *,
    empty_message: str,
    unreadable_message: str,
    empty_bytes_message: str,
) -> bytes:
    """
    Decode the first image from an Images API response.

    Args:
        response: Provider response with ``data[0].b64_json``.
        empty_message: Error when no b64 payload is present.
        unreadable_message: Error when base64 cannot be decoded.
        empty_bytes_message: Error when decoded bytes are empty.

    Returns:
        Decoded image bytes.

    Raises:
        ImageGenerationError: When the payload is missing or unusable.
    """
    data = first_images_api_b64(response)
    if not data:
        raise ImageGenerationError(empty_message)
    try:
        decoded = base64.b64decode(data, validate=True)
    except Exception as exc:
        raise ImageGenerationError(unreadable_message) from exc
    if not decoded:
        raise ImageGenerationError(empty_bytes_message)
    return decoded


def map_images_api_bad_request(exc: openai.BadRequestError) -> ImageGenerationError:
    """
    Map an Images API ``BadRequestError`` to a chat-facing error.

    Args:
        exc: Provider bad-request exception.

    Returns:
        ``ImageGenerationError`` with policy or generic refusal text.
    """
    code = _provider_error_code(exc)
    logger.warning(
        "Images API refused (code=%s): %s", code or "unknown", exc
    )
    if _is_policy_refusal(exc):
        return ImageGenerationError(_POLICY_REFUSAL_MESSAGE)
    return ImageGenerationError(_GENERIC_REFUSAL_MESSAGE)
