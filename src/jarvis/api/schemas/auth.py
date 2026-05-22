"""Pydantic schemas for authentication (JWT)."""

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    """POST /token response after successful Basic login."""

    access_token: str = Field(description="JWT firmado.")
    token_type: str = Field(default="bearer", description="Tipo OAuth2 (siempre bearer).")
