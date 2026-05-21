"""ChatService authorization messages (Spanish, action-specific)."""

import pytest
from fastapi import HTTPException

from api.services.chat_service import ChatService


def test_non_admin_cannot_reset_other_thread():
    user = {"real_name": "Alice", "admin": False}
    with pytest.raises(HTTPException) as exc:
        ChatService()._resolve_thread_id("Bob", user, action="reset")
    assert exc.value.status_code == 403
    assert "reiniciar la memoria" in exc.value.detail


def test_non_admin_cannot_read_other_thread_history():
    user = {"real_name": "Alice", "admin": False}
    with pytest.raises(HTTPException) as exc:
        ChatService()._resolve_thread_id("Bob", user, action="read")
    assert exc.value.status_code == 403
    assert "historial" in exc.value.detail
