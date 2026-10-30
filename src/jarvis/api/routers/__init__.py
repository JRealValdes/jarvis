"""FastAPI routers by domain (auth, chat, admin)."""

from jarvis.api.routers import admin, auth, chat, images

__all__ = ["admin", "auth", "chat", "images"]
