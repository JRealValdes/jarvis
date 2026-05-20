"""Rutas administrativas (caché global, resets)."""

from fastapi import APIRouter, Depends

from api.dependencies import require_admin
from api.services.admin_service import admin_service

router = APIRouter(tags=["admin"])


@router.post("/admin/reset-global-memory")
async def reset_memory_global(user: dict = Depends(require_admin)) -> dict:
    """
    Vacía todas las cachés de agentes y sesiones (solo admin).

    Args:
        user: Payload JWT (debe ser admin).

    Returns:
        Dict ``{status, message}``.
    """
    return admin_service.reset_global_memory()


@router.get("/admin/cache-status")
async def admin_cache_status(user: dict = Depends(require_admin)) -> dict:
    """
    Estado de cachés globales (solo admin).

    Args:
        user: Payload JWT (debe ser admin).

    Returns:
        Dict de contadores y sesiones en caché.
    """
    return admin_service.get_cache_status()
