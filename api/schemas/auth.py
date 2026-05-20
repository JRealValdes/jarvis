"""Esquemas Pydantic para autenticación (JWT)."""

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    """Respuesta de POST /token tras login Basic exitoso."""

    access_token: str = Field(description="JWT firmado.")
    token_type: str = Field(default="bearer", description="Tipo OAuth2 (siempre bearer).")
