"""Webhooks externos (WhatsApp / Twilio)."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import PlainTextResponse

from api.dependencies import verify_jwt_token
from api.services.chat_service import chat_service

router = APIRouter(tags=["webhooks"])


@router.post("/whatsapp")
async def whatsapp_webhook(
    request: Request,
    Body: str = Form(...),
    From: str = Form(...),
    ProfileName: str = Form(None),
    user: dict = Depends(verify_jwt_token),
) -> PlainTextResponse:
    """
    Webhook Twilio/WhatsApp: reenvía el cuerpo del mensaje a Jarvis.

    Args:
        request: Request FastAPI (reservado para extensiones).
        Body: Texto del mensaje entrante.
        From: Identificador del remitente (usado como thread_id).
        ProfileName: Nombre de perfil WhatsApp (opcional).
        user: Payload JWT.

    Returns:
        PlainTextResponse con respuestas unidas por saltos de línea.
    """
    text = chat_service.whatsapp_reply(Body, From, user)
    return PlainTextResponse(text)
