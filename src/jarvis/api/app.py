"""FastAPI Jarvis application bootstrap.

``jarvis.core.config`` is imported before other Jarvis modules so ``.env``
loads once (see that module).
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import logging

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from jarvis.core.config import API_PORT, USE_MCP
from jarvis.agents.mcp_session import get_mcp_tool_session
from jarvis.agents.session import invalidate_agents_cache
from jarvis.api.errors import ForbiddenError
from jarvis.core.logging_config import configure_logging

configure_logging()
from jarvis.api.routers import admin, auth, chat, images

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _lifespan(_application: FastAPI) -> AsyncIterator[None]:
    """
    Open the MCP tool session for the process and close it on shutdown.

    Args:
        _application: FastAPI instance (unused; required by the lifespan hook).
    """
    _purge_expired_images()
    if USE_MCP:
        await get_mcp_tool_session().connect()
    try:
        yield
    finally:
        await invalidate_agents_cache()
        await get_mcp_tool_session().close()


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
        lifespan=_lifespan,
    )

    @application.exception_handler(ForbiddenError)
    async def _forbidden_handler(
        _request: Request, exc: ForbiddenError
    ) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": exc.detail})

    application.include_router(auth.router)
    application.include_router(chat.router)
    application.include_router(admin.router)
    application.include_router(images.router)
    return application


def _purge_expired_images() -> None:
    """Drop expired assistant images when the API process starts."""
    try:
        from jarvis.infrastructure.images.store import purge_expired

        removed = purge_expired()
    except Exception:
        logger.warning("Could not purge expired stored images.", exc_info=True)
        return
    if removed:
        logger.info("Removed %s expired stored image(s).", removed)


app = create_app()


def start_uvicorn() -> None:
    """Start the ASGI server on 0.0.0.0:API_PORT (blocking)."""
    uvicorn.run(app, host="0.0.0.0", port=API_PORT)


def main() -> None:
    """CLI entry point: start uvicorn (LAN / localhost; off-LAN is host-layer, e.g. Tailscale)."""
    start_uvicorn()


if __name__ == "__main__":
    main()
