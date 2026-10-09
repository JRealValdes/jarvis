"""Global Jarvis configuration (default model, JWT, debug flags)."""

from jarvis.core.enums import IdentificationFailedProtocolEnum, ModelEnum

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

USE_MCP: bool = False
"""If True, OpenAI agents also receive tools from the process-wide MCP session."""
