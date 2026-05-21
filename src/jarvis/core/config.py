"""Global Jarvis configuration (default model, JWT, debug flags)."""

from core.enums import IdentificationFailedProtocolEnum, ModelEnum

DEFAULT_MODEL: ModelEnum = ModelEnum.GPT_3_5
"""LLM used when the client does not specify another model."""

IDENTIFICATION_FAILED_PROTOCOL: IdentificationFailedProtocolEnum = (
    IdentificationFailedProtocolEnum.AUTOMATIC_RESPONSE
)
"""Behavior when the user is not identified in a session."""

DB_DEBUG_MODE: bool = False
"""If True, allows debug operations on the user database."""

EXPOSE_API_WITH_CLOUDFLARED: bool = True
"""If True, the API attempts cloudflared exposure on startup."""

JWT_ALGORITHM: str = "HS256"
"""Signing algorithm for JWT tokens."""

JWT_EXP_DELTA_SECONDS: int = 3600
"""JWT lifetime in seconds (one hour by default)."""

USE_MCP: bool = False
"""If True, the GPT-3.5 agent uses JarvisMcpMemoryAgent instead of JarvisMemoryAgent."""
