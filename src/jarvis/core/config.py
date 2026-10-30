"""Jarvis settings: the only module that loads ``.env`` and reads the environment.

``load_dotenv()`` runs once, on import. Entry points (``jarvis.__main__``,
root ``app.py``, and ``jarvis.api.app``) import this module before other
Jarvis code so a local ``.env`` is applied before settings are read.

Public variable names stay as documented in ``.env.example`` (``JARVIS_*``,
``JWT_*``, ``API_PORT``, ``FERNET_KEY``).
``OPENAI_API_KEY`` is read by the OpenAI client, not by Jarvis.
``LANGSMITH_*`` is read by the LangSmith SDK for optional tracing (documented
in ``.env.example`` / README). Add new Jarvis settings here instead of
calling ``os.getenv`` elsewhere.
"""

from __future__ import annotations

import os
from enum import Enum
from typing import TypeVar

from dotenv import load_dotenv

from jarvis.core.enums import IdentificationFailedProtocolEnum, ModelEnum

load_dotenv()

EnumT = TypeVar("EnumT", bound=Enum)


def _env_flag(name: str, default: bool = False) -> bool:
    """
    Parse a boolean environment variable.

    Args:
        name: Environment variable name.
        default: Value when the variable is unset or empty.

    Returns:
        True for ``1``, ``true``, ``yes``, or ``on`` (case-insensitive).
    """
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_optional(name: str) -> str | None:
    """
    Read an optional string environment variable.

    Args:
        name: Environment variable name.

    Returns:
        Stripped value, or None when unset or empty.
    """
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return None
    return raw.strip()


def _env_str(name: str, default: str) -> str:
    """
    Read a string environment variable.

    Args:
        name: Environment variable name.
        default: Value when unset or empty.

    Returns:
        Stripped value, or ``default``.
    """
    value = _env_optional(name)
    if value is None:
        return default
    return value


def require_env(name: str) -> str:
    """
    Read a required string environment variable.

    Args:
        name: Environment variable name.

    Returns:
        Stripped value.

    Raises:
        RuntimeError: If the variable is unset or empty.
    """
    value = _env_optional(name)
    if value is None:
        raise RuntimeError(f"{name} is not set")
    return value


def _env_non_negative_int(name: str, default: int) -> int:
    """
    Read an integer environment variable that must be zero or greater.

    Args:
        name: Environment variable name.
        default: Value when unset or empty.

    Returns:
        Parsed integer.

    Raises:
        ValueError: If the variable is not an integer or is negative.
    """
    value = _env_int(name, default)
    if value < 0:
        raise ValueError(f"{name} must be >= 0 (0 means never expire).")
    return value


def _env_image_model(name: str, default: str) -> str:
    """
    Read the OpenAI image model id.

    Args:
        name: Environment variable name.
        default: Value when unset or empty.

    Returns:
        Model id.

    Raises:
        ValueError: If the id is a DALL·E model.
    """
    value = _env_str(name, default)
    lowered = value.lower()
    if lowered.startswith("dall-e") or lowered.startswith("dalle"):
        raise ValueError(f"{name} must be a gpt-image model, not {value!r}.")
    return value


def _env_choice(name: str, default: str, allowed: frozenset[str]) -> str:
    """
    Read a string environment variable that must be one of ``allowed``.

    Args:
        name: Environment variable name.
        default: Value when unset or empty.
        allowed: Accepted values.

    Returns:
        Stripped value.

    Raises:
        ValueError: If the value is not in ``allowed``.
    """
    value = _env_str(name, default)
    if value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ValueError(f"Invalid {name}={value!r}. Expected one of: {choices}.")
    return value


def _env_int(name: str, default: int) -> int:
    """
    Read an integer environment variable.

    Args:
        name: Environment variable name.
        default: Value when unset or empty.

    Returns:
        Parsed integer, or ``default``.

    Raises:
        ValueError: If the variable is set but is not an integer.
    """
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw.strip())


def _env_enum(name: str, enum_cls: type[EnumT], default: EnumT) -> EnumT:
    """
    Read an enum member from the environment by member name.

    Args:
        name: Environment variable name.
        enum_cls: Enum type to resolve.
        default: Member when unset or empty.

    Returns:
        Enum member.

    Raises:
        ValueError: If the value is not a member name of ``enum_cls``.
    """
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    key = raw.strip().upper()
    try:
        return enum_cls[key]
    except KeyError as exc:
        valid = ", ".join(member.name for member in enum_cls)
        raise ValueError(
            f"Invalid {name}={raw!r}. Expected one of: {valid}."
        ) from exc


DEFAULT_MODEL: ModelEnum = _env_enum(
    "JARVIS_DEFAULT_MODEL", ModelEnum, ModelEnum.GPT_4O_MINI
)
"""LLM used when the client does not specify another model."""

LOCAL_THREAD_ID: str = _env_str("JARVIS_LOCAL_THREAD_ID", "1")
"""Conversation thread for the CLI and Gradio. Override with ``JARVIS_LOCAL_THREAD_ID``."""

IDENTIFICATION_FAILED_PROTOCOL: IdentificationFailedProtocolEnum = _env_enum(
    "JARVIS_IDENTIFICATION_FAILED_PROTOCOL",
    IdentificationFailedProtocolEnum,
    IdentificationFailedProtocolEnum.AUTOMATIC_RESPONSE,
)
"""Behavior when the user is not identified in a session."""

DB_DEBUG_MODE: bool = _env_flag("JARVIS_DB_DEBUG_MODE", default=False)
"""If True, allows debug operations on the user database."""

JWT_ALGORITHM: str = _env_str("JWT_ALGORITHM", "HS256")
"""Signing algorithm for JWT tokens."""

JWT_EXP_DELTA_SECONDS: int = _env_int("JWT_EXP_DELTA_SECONDS", 3600)
"""JWT lifetime in seconds (one hour by default)."""

USE_MCP: bool = _env_flag("JARVIS_USE_MCP", default=False)
"""If True, OpenAI agents also receive tools from the process-wide MCP session."""

SHOW_TOOL_TRACES: bool = _env_flag("JARVIS_SHOW_TOOL_TRACES", default=False)
"""If True, chat history includes tool call/result messages. Default: final replies only."""

RANKED_IMAGE_RETRIEVAL: bool = _env_flag(
    "JARVIS_RANKED_IMAGE_RETRIEVAL", default=False
)
"""If True, image search scores a larger pool before returning the top hits."""

VISION_VERIFY_IMAGES: bool = _env_flag(
    "JARVIS_VISION_VERIFY_IMAGES", default=False
)
"""If True, one vision call per turn must accept the best web image before it is shown."""

IMAGE_STORAGE: bool = _env_flag("JARVIS_IMAGE_STORAGE", default=True)
"""If True, assistant images are saved on disk and served by Jarvis instead of hotlinked."""

WEB_IMAGE_TTL_DAYS: int = _env_non_negative_int("JARVIS_WEB_IMAGE_TTL_DAYS", 30)
"""How long a stored web-search image is kept. ``0`` means never auto-delete."""

GENERATED_IMAGE_TTL_DAYS: int = _env_non_negative_int(
    "JARVIS_GENERATED_IMAGE_TTL_DAYS", 365
)
"""How long a stored generated image is kept. ``0`` means never auto-delete."""

IMAGE_GENERATION_MODEL: str = _env_image_model(
    "JARVIS_IMAGE_MODEL", "gpt-image-1-mini"
)
"""OpenAI image model for admin generation. DALL·E model ids are rejected."""

IMAGE_GENERATION_QUALITY: str = _env_choice(
    "JARVIS_IMAGE_QUALITY",
    "low",
    frozenset({"low", "medium", "high", "auto"}),
)
"""Quality sent to the Images API. ``low`` is the cheaper default."""

IMAGE_GENERATION_SIZE: str = _env_choice(
    "JARVIS_IMAGE_SIZE",
    "1024x1024",
    frozenset({"1024x1024", "1024x1536", "1536x1024", "auto"}),
)
"""Pixel size sent to the Images API."""

API_PORT: int = _env_int("API_PORT", 8000)
"""HTTP port for the FastAPI server."""


def get_jwt_secret_key() -> str:
    """
    Read the JWT signing key.

    Returns:
        Value of ``JWT_SECRET_KEY``.

    Raises:
        RuntimeError: If the variable is not set.
    """
    return require_env("JWT_SECRET_KEY")


def get_fernet_key() -> str:
    """
    Read the Fernet key used to encrypt user fields.

    Returns:
        Value of ``FERNET_KEY``.

    Raises:
        RuntimeError: If the variable is not set.
    """
    return require_env("FERNET_KEY")
