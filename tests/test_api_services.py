"""API service tests (no LLM or database)."""

from jarvis.api.services.auth_service import AuthService
from jarvis.api.services.chat_service import ChatService
from jarvis.api.services.admin_service import AdminService


def test_auth_service_validate_response_shape():
    user = {"sub": "u", "real_name": "R", "admin": False}
    body = AuthService().build_validate_token_response(user)
    assert body["status"] == "ok"
    assert body["user"] == user


def test_chat_service_resolve_thread_id_default():
    user = {"real_name": "Alice", "admin": False}
    tid = ChatService()._resolve_thread_id(None, user, action="read")
    assert tid == "Alice"


def test_admin_service_instances_exported():
    from jarvis.api.services import admin_service, auth_service, chat_service

    assert isinstance(auth_service, AuthService)
    assert isinstance(chat_service, ChatService)
    assert isinstance(admin_service, AdminService)
