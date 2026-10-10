"""Administrative use cases (global cache)."""

from jarvis.agents.session import get_cache_status, reset_cache


class AdminService:
    """Operations restricted to admin users."""

    async def reset_global_memory(self) -> dict:
        """
        Clear agent caches, delete persisted checkpoints, and close MCP.

        Returns:
            Dict ``{status, message}``.
        """
        await reset_cache()
        return {"status": "ok", "message": "Global memory reset"}

    def get_cache_status(self) -> dict:
        """
        Summarize global cache state.

        Returns:
            Dict with counters and lists of active models/sessions.
        """
        return get_cache_status()


admin_service = AdminService()
