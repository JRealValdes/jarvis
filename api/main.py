"""FastAPI Jarvis application bootstrap."""

from dotenv import load_dotenv

load_dotenv()

import uvicorn
from fastapi import FastAPI

from api.deployment import API_PORT, run_with_optional_tunnel
from core.logging_config import configure_logging

configure_logging()
from api.routers import admin, auth, chat, webhooks


def create_app() -> FastAPI:
    """
    Build the FastAPI instance with all routers registered.

    Returns:
        Configured FastAPI application.
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
    """Start the ASGI server on 0.0.0.0:API_PORT (blocking)."""
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)


def main() -> None:
    """CLI entry point: optional tunnel plus uvicorn."""
    run_with_optional_tunnel(start_uvicorn)


if __name__ == "__main__":
    main()
