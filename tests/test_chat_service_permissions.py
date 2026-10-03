"""ChatService authorization (action-specific ForbiddenError)."""

import pytest

from jarvis.api.errors import ForbiddenError
from jarvis.api.services.chat_service import ChatService


def test_non_admin_cannot_reset_other_thread():
    user = {"real_name": "Alice", "admin": False}
    with pytest.raises(ForbiddenError) as exc:
        ChatService()._resolve_thread_id("Bob", user, action="reset")
    assert "reset other users" in str(exc.value).lower()


def test_non_admin_cannot_read_other_thread_history():
    user = {"real_name": "Alice", "admin": False}
    with pytest.raises(ForbiddenError) as exc:
        ChatService()._resolve_thread_id("Bob", user, action="read")
    assert "history" in str(exc.value).lower()
