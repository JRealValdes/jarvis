"""HTTP routes for push device token registration."""

from typing import Any

from fastapi import APIRouter, Depends

from jarvis.api.dependencies import verify_jwt_token
from jarvis.api.schemas.devices import (
    DeviceRegisterInput,
    DeviceRegisterOut,
    DeviceUnregisterInput,
)
from jarvis.api.services.devices_service import devices_service

router = APIRouter(prefix="/devices", tags=["devices"])


@router.post("/register", response_model=DeviceRegisterOut)
async def register_device(
    body: DeviceRegisterInput,
    user: dict[str, Any] = Depends(verify_jwt_token),
) -> DeviceRegisterOut:
    """Register or refresh an FCM/APNs device token for the user."""
    return devices_service.register(body, user)


@router.post("/unregister")
async def unregister_device(
    body: DeviceUnregisterInput,
    user: dict[str, Any] = Depends(verify_jwt_token),
) -> dict[str, str]:
    """Remove a device token owned by the authenticated user."""
    return devices_service.unregister(body, user)
