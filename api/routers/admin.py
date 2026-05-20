"""Rutas administrativas (caché global, resets)."""

from fastapi import APIRouter, Depends, HTTPException, status

from agents.session import get_cache_status, reset_cache_global
from api.dependencies import verify_jwt_token

router = APIRouter(tags=["admin"])


def _require_admin(user: dict) -> None:
    """
    Comprueba privilegio admin en el payload JWT.

    Args:
        user: Claims decodificados.

    Raises:
        HTTPException: 403 si admin es falso o ausente.
    """
    if not user.get("admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to perform this action.",
        )


@router.post("/admin/reset-global-memory")
async def reset_memory_global(user: dict = Depends(verify_jwt_token)) -> dict:
    """
    Vacía todas las cachés de agentes y sesiones (solo admin).

    Args:
        user: Payload JWT.

    Returns:
        Dict ``{status, message}``.

    Raises:
        HTTPException: 403 si el usuario no es admin.
    """
    _require_admin(user)
    reset_cache_global()
    print("Limpieza exitosa")
    return {"status": "ok", "message": "Global memory reset"}


@router.get("/admin/cache-status")
async def admin_cache_status(user: dict = Depends(verify_jwt_token)) -> dict:
    """
    Estado de cachés globales (solo admin).

    Args:
        user: Payload JWT.

    Returns:
        Dict de ``get_cache_status()``.

    Raises:
        HTTPException: 403 si no es admin.
    """
    _require_admin(user)
    return get_cache_status()
