"""Bootstrap de la aplicación FastAPI Jarvis."""

import uvicorn
from fastapi import FastAPI

from api.deployment import API_PORT, run_with_optional_tunnel
from api.routers import admin, auth, chat, webhooks


def create_app() -> FastAPI:
    """
    Construye la instancia FastAPI con todos los routers registrados.

    Returns:
        Aplicación FastAPI configurada.
    """
    application = FastAPI(
        title="Jarvis API",
        description="API backend for Jarvis",
        version="1.0.0",
    )
    application.include_router(auth.router)
    application.include_router(chat.router)
    application.include_router(webhooks.router)
    application.include_router(admin.router)
    return application


app = create_app()


def start_uvicorn() -> None:
    """Arranca el servidor ASGI en 0.0.0.0:API_PORT (bloqueante)."""
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)


def main() -> None:
    """Punto de entrada CLI: túnel opcional + uvicorn."""
    run_with_optional_tunnel(start_uvicorn)


if __name__ == "__main__":
    main()
