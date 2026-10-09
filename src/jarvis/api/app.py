"""FastAPI Jarvis application bootstrap."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from jarvis.agents.mcp_session import get_mcp_tool_session
from jarvis.api.deployment import API_PORT, run_with_optional_tunnel
from jarvis.api.errors import ForbiddenError
from jarvis.core.config import USE_MCP
from jarvis.core.logging_config import configure_logging

configure_logging()
from jarvis.api.routers import admin, auth, chat


@asynccontextmanager
async def _lifespan(_application: FastAPI) -> AsyncIterator[None]:
    """
    Open the MCP tool session for the process and close it on shutdown.

    Args:
        _application: FastAPI instance (unused; required by the lifespan hook).
    """
    if USE_MCP:
        await get_mcp_tool_session().aconnect()
    try:
        yield
    finally:
        await get_mcp_tool_session().aclose()


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
