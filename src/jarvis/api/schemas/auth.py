"""Pydantic schemas for authentication (JWT)."""

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    """POST /token response after successful Basic login."""

    access_token: str = Field(description="Signed JWT.")
    token_type: str = Field(
        default="bearer", description="OAuth2 type (always bearer)."
    )
