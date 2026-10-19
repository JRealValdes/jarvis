"""Jarvis settings: the only module that loads ``.env`` and reads the environment.

``load_dotenv()`` runs once, on import. Entry points (``jarvis.__main__``,
root ``app.py``, and ``jarvis.api.app``) import this module before other
Jarvis code so a local ``.env`` is applied before settings are read.

Public variable names stay as documented in ``.env.example`` (``JARVIS_*``,
``JWT_*``, ``API_PORT``, ``TELEGRAM_*``, ``FIREBASE_*``, ``FERNET_KEY``).
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

SHOW_TOOL_TRACES: bool = _env_flag("JARVIS_SHOW_TOOL_TRACES", default=False)
"""If True, chat history includes tool call/result messages. Default: final replies only."""

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


def get_telegram_bot_token() -> str | None:
    """
    Read the Telegram bot token.

    Returns:
        Token string, or None when notifications are not configured.
    """
    return _env_optional("TELEGRAM_BOT_TOKEN")


def get_telegram_chat_id() -> str | None:
    """
    Read the Telegram chat id that receives deployment notices.

    Returns:
        Chat id, or None when notifications are not configured.
    """
    return _env_optional("TELEGRAM_CHAT_ID")


def get_firebase_db_url() -> str | None:
    """
    Read the Firebase Realtime Database URL.

    Returns:
        Database URL, or None when URL sharing is not configured.
    """
    return _env_optional("FIREBASE_DB_URL")


def get_firebase_node_path() -> str:
    """
    Read the Firebase node that stores the latest public API URL.

    Returns:
        Node path, defaulting to ``jarvis/latest_url``.
    """
    return _env_str("FIREBASE_NODE_PATH", "jarvis/latest_url")
