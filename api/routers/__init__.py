"""FastAPI routers by domain (auth, chat, webhooks, admin)."""

from api.routers import admin, auth, chat, webhooks

__all__ = ["admin", "auth", "chat", "webhooks"]
