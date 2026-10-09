"""Administrative use cases (global cache)."""

from jarvis.agents.session import areset_cache, get_cache_status


class AdminService:
    """Operations restricted to admin users."""

    async def reset_global_memory(self) -> dict:
        """
        Clear all agent and session caches and close the MCP tool session.

        Returns:
            Dict ``{status, message}``.
        """
        await areset_cache()
        return {"status": "ok", "message": "Global memory reset"}

    def get_cache_status(self) -> dict:
        """
        Summarize global cache state.

        Returns:
            Dict with counters and lists of active models/sessions.
        """
        return get_cache_status()


admin_service = AdminService()
