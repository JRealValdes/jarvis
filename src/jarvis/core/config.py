"""Jarvis settings: environment variables with typed defaults.

Import this module after secrets are available. ``load_dotenv()`` runs on
import so a local ``.env`` is picked up for CLI, Gradio, and the API.
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


def _env_str(name: str, default: str) -> str:
    """
    Read a string environment variable.

    Args:
        name: Environment variable name.
        default: Value when unset or empty.

    Returns:
        Stripped value, or ``default``.
    """
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip()


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

IDENTIFICATION_FAILED_PROTOCOL: IdentificationFailedProtocolEnum = _env_enum(
    "JARVIS_IDENTIFICATION_FAILED_PROTOCOL",
    IdentificationFailedProtocolEnum,
    IdentificationFailedProtocolEnum.AUTOMATIC_RESPONSE,
)
"""Behavior when the user is not identified in a session."""

DB_DEBUG_MODE: bool = _env_flag("JARVIS_DB_DEBUG_MODE", default=False)
"""If True, allows debug operations on the user database."""

EXPOSE_API_WITH_CLOUDFLARED: bool = _env_flag(
    "JARVIS_EXPOSE_API_WITH_CLOUDFLARED", default=False
)
"""If True, the API attempts cloudflared exposure on startup (opt-in)."""

JWT_ALGORITHM: str = _env_str("JWT_ALGORITHM", "HS256")
"""Signing algorithm for JWT tokens."""

JWT_EXP_DELTA_SECONDS: int = _env_int("JWT_EXP_DELTA_SECONDS", 3600)
"""JWT lifetime in seconds (one hour by default)."""

USE_MCP: bool = _env_flag("JARVIS_USE_MCP", default=False)
"""If True, OpenAI agents also receive tools from the process-wide MCP session."""

API_PORT: int = _env_int("API_PORT", 8000)
"""HTTP port for the FastAPI server."""
