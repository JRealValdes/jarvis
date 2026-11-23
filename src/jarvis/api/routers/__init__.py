"""FastAPI routers by domain (auth, chat, tasks, admin)."""

from jarvis.api.routers import admin, auth, chat, images, tasks

__all__ = ["admin", "auth", "chat", "images", "tasks"]
