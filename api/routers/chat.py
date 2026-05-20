"""Rutas de conversación con Jarvis y gestión de sesión en caché."""

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from agents.session import (
    ask_jarvis,
    check_individual_session_cache_exists,
    get_message_history,
    reset_session,
)
from api.dependencies import verify_jwt_token
from api.schemas.chat import AskInput, ThreadIdPayload
from enums.core_enums import ModelEnum

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
    model_enum = ModelEnum[input_data.model_name]
    thread_id = input_data.thread_id or user["real_name"]
    answer = ask_jarvis(input_data.message, model_enum, thread_id, user_info=user)
    return {"response": answer}


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
    thread_id = payload.thread_id if payload else None
    print(f"Realizando reset session con thread_id: {thread_id}")
    if thread_id:
        if not user.get("admin", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to reset memory for other users.",
            )
    else:
        thread_id = user["real_name"]
    reset_session(thread_id)
    print(f"Limpieza exitosa del thread id: {thread_id}")
    return {"status": "ok", "message": "Memory reset"}


@router.get("/individual-cache-status")
async def individual_cache_status(user: dict = Depends(verify_jwt_token)) -> JSONResponse:
    """
    Indica si existe sesión en caché para el real_name del JWT.

    Args:
        user: Payload JWT.

    Returns:
        JSON ``{exists: bool}``.
    """
    exists = check_individual_session_cache_exists(user["real_name"])
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
    if thread_id:
        if not user.get("admin", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to reset memory for other users.",
            )
    else:
        thread_id = user["real_name"]

    history = get_message_history(thread_id)
    return {"thread_id": thread_id, "messages": history}
