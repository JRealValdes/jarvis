"""FastAPI routers by domain (auth, chat, tasks, devices, jobs, admin)."""

from jarvis.api.routers import admin, auth, chat, devices, images, jobs, tasks

__all__ = ["admin", "auth", "chat", "devices", "images", "jobs", "tasks"]
