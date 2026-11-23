"""Device token registration use cases."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from jarvis.api.schemas.devices import (
    DeviceRegisterInput,
    DeviceRegisterOut,
    DeviceTokenOut,
    DeviceUnregisterInput,
)
from jarvis.infrastructure.persistence.devices.repository import (
    register_device_token,
    unregister_device_token,
)


class DevicesService:
    """Owner-scoped push device registration."""

    def register(
        self, body: DeviceRegisterInput, user: dict[str, Any]
    ) -> DeviceRegisterOut:
        """
        Register or refresh a device token for the user.

        Args:
            body: Token + platform.
            user: JWT claims.

        Returns:
            Registration result.

        Raises:
            HTTPException: 400 on validation errors.
        """
        try:
            record = register_device_token(
                owner_real_name=user["real_name"],
                token=body.token,
                platform=body.platform,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return DeviceRegisterOut(
            status="ok",
            device=DeviceTokenOut(
                token=record.token,
                platform=record.platform,
                created_at=record.created_at,
                updated_at=record.updated_at,
            ),
        )

    def unregister(
        self, body: DeviceUnregisterInput, user: dict[str, Any]
    ) -> dict[str, str]:
        """
        Remove a device token owned by the user.

        Args:
            body: Token to remove.
            user: JWT claims.

        Returns:
            Status dict.
        """
        unregister_device_token(
            owner_real_name=user["real_name"], token=body.token
        )
        return {"status": "ok", "message": "Device unregistered"}


devices_service = DevicesService()
