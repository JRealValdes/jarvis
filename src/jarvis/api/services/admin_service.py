"""Administrative use cases (global cache)."""

from jarvis.agents.session import get_cache_status, reset_cache_global


class AdminService:
    """Operations restricted to admin users."""

    def reset_global_memory(self) -> dict:
        """
        Clear all agent and session caches.

        Returns:
            Dict ``{status, message}``.
        """
        reset_cache_global()
        return {"status": "ok", "message": "Memoria global reiniciada"}

    def get_cache_status(self) -> dict:
        """
        Summarize global cache state.

        Returns:
            Dict with counters and lists of active models/sessions.
        """
        return get_cache_status()


admin_service = AdminService()
