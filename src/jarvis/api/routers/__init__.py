"""FastAPI routers by domain (auth, chat, admin)."""

from jarvis.api.routers import admin, auth, chat

__all__ = ["admin", "auth", "chat"]
