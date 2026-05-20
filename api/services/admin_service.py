"""Casos de uso administrativos (caché global)."""

from agents.session import get_cache_status, reset_cache_global


class AdminService:
    """Operaciones restringidas a usuarios admin."""

    def reset_global_memory(self) -> dict:
        """
        Vacía todas las cachés de agentes y sesiones.

        Returns:
            Dict ``{status, message}``.
        """
        reset_cache_global()
        print("Limpieza exitosa")
        return {"status": "ok", "message": "Global memory reset"}

    def get_cache_status(self) -> dict:
        """
        Resume el estado de cachés globales.

        Returns:
            Dict con contadores y listas de modelos/sesiones activas.
        """
        return get_cache_status()


admin_service = AdminService()
