"""
Shim de compatibilidad.

Preferir ``python -m api.main`` o ``from api.main import app``.
"""

from api.deployment import (
    API_PORT,
    expose_api_with_cloudflared,
    save_url_to_firebase,
    send_telegram_message,
)
from api.main import app, main, start_uvicorn

__all__ = [
    "app",
    "API_PORT",
    "start_uvicorn",
    "main",
    "expose_api_with_cloudflared",
    "save_url_to_firebase",
    "send_telegram_message",
]

if __name__ == "__main__":
    main()
