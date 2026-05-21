"""Configuración global de Jarvis (modelo por defecto, JWT, flags de depuración)."""

from core.enums.core_enums import IdentificationFailedProtocolEnum, ModelEnum

DEFAULT_MODEL: ModelEnum = ModelEnum.GPT_3_5
"""Modelo LLM usado cuando el cliente no especifica otro."""

IDENTIFICATION_FAILED_PROTOCOL: IdentificationFailedProtocolEnum = (
    IdentificationFailedProtocolEnum.AUTOMATIC_RESPONSE
)
"""Comportamiento cuando el usuario no se identifica en la sesión."""

DB_DEBUG_MODE: bool = False
"""Si es True, permite operaciones de depuración sobre la base de usuarios."""

EXPOSE_API_WITH_CLOUDFLARED: bool = True
"""Si es True, al arrancar la API intenta exponerla con cloudflared."""

JWT_ALGORITHM: str = "HS256"
"""Algoritmo de firma para tokens JWT."""

JWT_EXP_DELTA_SECONDS: int = 3600
"""Duración del token JWT en segundos (1 hora por defecto)."""

USE_MCP: bool = False
"""Si es True, el agente GPT-3.5 usa JarvisMcpMemoryAgent en lugar de JarvisMemoryAgent."""
