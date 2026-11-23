"""Pydantic schemas for push device registration."""

from pydantic import BaseModel, Field


class DeviceRegisterInput(BaseModel):
    """Register or refresh a push device token."""

    token: str = Field(..., min_length=1)
    platform: str = Field(..., description="android | ios | web")


class DeviceUnregisterInput(BaseModel):
    """Remove a push device token."""

    token: str = Field(..., min_length=1)


class DeviceTokenOut(BaseModel):
    """Stored device token (token redacted in lists if needed later)."""

    token: str
    platform: str
    created_at: str
    updated_at: str


class DeviceRegisterOut(BaseModel):
    """Response after registering a device."""

    status: str
    device: DeviceTokenOut
