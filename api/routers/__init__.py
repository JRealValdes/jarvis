"""Routers FastAPI por dominio (auth, chat, webhooks, admin)."""

from api.routers import admin, auth, chat, webhooks

__all__ = ["admin", "auth", "chat", "webhooks"]
