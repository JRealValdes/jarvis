"""Tests for router registration on the FastAPI application."""

from jarvis.api.main import app
from jarvis.api.routers import admin, auth, chat


def test_routers_have_expected_route_count():
    assert len(auth.router.routes) == 2
    assert len(chat.router.routes) == 4
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
        "/admin/reset-global-memory",
        "/admin/cache-status",
    ):
        assert path in paths
