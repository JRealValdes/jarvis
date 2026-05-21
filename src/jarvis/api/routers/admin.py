"""Administrative routes (global cache, resets)."""

from fastapi import APIRouter, Depends

from jarvis.api.dependencies import require_admin
from jarvis.api.services.admin_service import admin_service

router = APIRouter(tags=["admin"])


@router.post("/admin/reset-global-memory")
async def reset_memory_global(user: dict = Depends(require_admin)) -> dict:
    """
    Clear all agent and session caches (admin only).

    Args:
        user: JWT payload (must be admin).

    Returns:
        Dict ``{status, message}``.
    """
    return admin_service.reset_global_memory()


@router.get("/admin/cache-status")
async def admin_cache_status(user: dict = Depends(require_admin)) -> dict:
    """
    Global cache status (admin only).

    Args:
        user: JWT payload (must be admin).

    Returns:
        Dict of counters and cached sessions.
    """
    return admin_service.get_cache_status()
