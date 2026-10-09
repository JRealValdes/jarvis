"""Global Jarvis configuration (default model, JWT, debug flags)."""

import os

from jarvis.core.enums import IdentificationFailedProtocolEnum, ModelEnum


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


DEFAULT_MODEL: ModelEnum = ModelEnum.GPT_4O_MINI
"""LLM used when the client does not specify another model."""


IDENTIFICATION_FAILED_PROTOCOL: IdentificationFailedProtocolEnum = (
    IdentificationFailedProtocolEnum.AUTOMATIC_RESPONSE
)
"""Behavior when the user is not identified in a session."""

DB_DEBUG_MODE: bool = False
"""If True, allows debug operations on the user database."""

EXPOSE_API_WITH_CLOUDFLARED: bool = False
"""If True, the API attempts cloudflared exposure on startup (opt-in)."""

JWT_ALGORITHM: str = "HS256"
"""Signing algorithm for JWT tokens."""

JWT_EXP_DELTA_SECONDS: int = 3600
"""JWT lifetime in seconds (one hour by default)."""

USE_MCP: bool = _env_flag("JARVIS_USE_MCP", default=False)
"""If True, OpenAI agents also receive tools from the process-wide MCP session.

Set with ``JARVIS_USE_MCP=1`` (or ``true`` / ``yes`` / ``on``) in the environment.
"""
