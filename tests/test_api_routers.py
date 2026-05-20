"""Tests de registro de routers en la aplicación FastAPI."""

from api.main import app
from api.routers import admin, auth, chat, webhooks


def test_routers_have_expected_route_count():
    assert len(auth.router.routes) == 2
    assert len(chat.router.routes) == 4
    assert len(webhooks.router.routes) == 1
    assert len(admin.router.routes) == 2


def test_app_includes_all_router_paths():
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    for path in (
        "/token",
        "/validate-token",
        "/ask",
        "/reset-session",
        "/individual-cache-status",
        "/message-history",
        "/whatsapp",
        "/admin/reset-global-memory",
        "/admin/cache-status",
    ):
        assert path in paths
