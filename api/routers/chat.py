"""Rutas de conversación con Jarvis y gestión de sesión en caché."""

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse

from api.dependencies import verify_jwt_token
from api.schemas.chat import AskInput, ThreadIdPayload
from api.services.chat_service import chat_service

router = APIRouter(tags=["chat"])


@router.post("/ask")
async def ask_json(
    input_data: AskInput,
    user: dict = Depends(verify_jwt_token),
) -> dict:
    """
    Envía un mensaje a Jarvis y devuelve la respuesta.

    Args:
        input_data: Mensaje, modelo y thread_id opcional.
        user: Payload JWT (dependencia).

    Returns:
        Dict con clave ``response`` (lista de strings).
    """
    return chat_service.ask(input_data, user)


@router.post("/reset-session")
async def reset_session_individual(
    payload: ThreadIdPayload | None = Body(default=None),
    user: dict = Depends(verify_jwt_token),
) -> dict:
    """
    Reinicia la memoria de sesión del usuario (o de otro hilo si es admin).

    Args:
        payload: thread_id opcional.
        user: Payload JWT.

    Returns:
        Dict ``{status, message}``.

    Raises:
        HTTPException: 403 si un no-admin intenta resetear otro hilo.
    """
    return chat_service.reset_session_for_user(payload, user)


@router.get("/individual-cache-status")
async def individual_cache_status(user: dict = Depends(verify_jwt_token)) -> JSONResponse:
    """
    Indica si existe sesión en caché para el real_name del JWT.

    Args:
        user: Payload JWT.

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
    Historial de mensajes parseado para un hilo.

    Args:
        thread_id: Hilo a consultar; por defecto real_name del JWT.
        user: Payload JWT.

    Returns:
        Dict ``{thread_id, messages}``.

    Raises:
        HTTPException: 403 si un no-admin consulta otro hilo.
    """
    return chat_service.get_history(thread_id, user)
