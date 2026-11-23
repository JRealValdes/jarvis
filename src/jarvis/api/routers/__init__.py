"""FastAPI routers by domain (auth, chat, tasks, devices, admin)."""

from jarvis.api.routers import admin, auth, chat, devices, images, tasks

__all__ = ["admin", "auth", "chat", "devices", "images", "tasks"]
