"""Smoke tests for FastAPI app route registration (no live LLM calls)."""

import jwt
from fastapi.testclient import TestClient

from api.main_api import app
from config import JWT_ALGORITHM


def _admin_token() -> str:
    payload = {
        "sub": "pytest-admin",
        "real_name": "Pytest Admin",
        "jarvis_name": "Sir",
        "is_female": False,
        "admin": True,
        "exp": 9999999999,
    }
    secret = __import__("os").environ["JWT_SECRET_KEY"]
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def test_app_has_documented_routes():
    paths = {route.path for route in app.routes if hasattr(route, "path")}
    expected = {
        "/token",
        "/ask",
        "/whatsapp",
        "/reset-session",
        "/admin/reset-global-memory",
        "/admin/cache-status",
        "/individual-cache-status",
        "/message-history",
        "/validate-token",
    }
    assert expected.issubset(paths)


def test_validate_token_requires_auth():
    client = TestClient(app)
    response = client.get("/validate-token")
    assert response.status_code == 403


def test_validate_token_with_bearer():
    client = TestClient(app)
    token = _admin_token()
    response = client.get(
        "/validate-token",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["user"]["admin"] is True


def test_individual_cache_status_route_name_is_unique():
    """Regression: second handler must not shadow admin cache_status."""
    get_routes = [r for r in app.routes if getattr(r, "methods", None) and "GET" in r.methods]
    cache_routes = [r for r in get_routes if r.path in ("/admin/cache-status", "/individual-cache-status")]
    assert len(cache_routes) == 2
    assert cache_routes[0].path != cache_routes[1].path
