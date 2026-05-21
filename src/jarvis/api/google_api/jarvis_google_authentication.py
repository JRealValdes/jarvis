"""Backward-compatible import path — prefer ``infrastructure.google.calendar_auth``."""

from jarvis.infrastructure.google.calendar_auth import (  # noqa: F401
    GOOGLE_API_DIR,
    get_authentications_for_user,
)

__all__ = ["GOOGLE_API_DIR", "get_authentications_for_user"]
