"""Jarvis conversation routes and cached session management."""

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from jarvis.api.dependencies import verify_jwt_token
from jarvis.api.schemas.chat import AskInput, ThreadIdPayload
from jarvis.api.services.chat_service import chat_service

router = APIRouter(tags=["chat"])


@router.post("/ask")
async def ask_json(
    input_data: AskInput,
    user: dict = Depends(verify_jwt_token),
) -> dict:
    """
    Send a message to Jarvis and return the reply.

    Args:
        input_data: Message, model, and optional thread_id.
        user: JWT payload (dependency).

    Returns:
        Dict with key ``response`` (list of strings).
    """
    return chat_service.ask(input_data, user)


@router.post("/reset-session")
async def reset_session_individual(
    payload: ThreadIdPayload | None = Body(default=None),
    user: dict = Depends(verify_jwt_token),
) -> dict:
    """
    Reset session memory for the user (or another thread if admin).

    Args:
        payload: Optional thread_id.
        user: JWT payload.

    Returns:
        Dict ``{status, message}``.

    Raises:
        HTTPException: 403 if a non-admin tries to reset another thread.
    """
    return chat_service.reset_session_for_user(payload, user)


@router.get("/individual-cache-status")
async def individual_cache_status(user: dict = Depends(verify_jwt_token)) -> JSONResponse:
    """
    Report whether a cached session exists for the JWT real_name.

    Args:
        user: JWT payload.

    Returns:
        JSON ``{exists: bool}``.
    """
    exists = chat_service.individual_cache_exists(user["real_name"])
    return JSONResponse(content={"exists": exists})


@router.get("/message-history")
async def message_history(
    thread_id: str | None = None,
    user: dict = Depends(verify_jwt_token),
) -> dict:
    """
    Parsed message history for a thread.

    Args:
        thread_id: Thread to query; defaults to JWT real_name.
        user: JWT payload.

    Returns:
        Dict ``{thread_id, messages}``.

    Raises:
        HTTPException: 403 if a non-admin queries another thread.
    """
    return chat_service.get_history(thread_id, user)
