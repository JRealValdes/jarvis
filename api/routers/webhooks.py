"""Webhooks externos (WhatsApp / Twilio)."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import PlainTextResponse

from agents.session import ask_jarvis
from api.dependencies import verify_jwt_token
from config import DEFAULT_MODEL

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
    responses = ask_jarvis(Body, DEFAULT_MODEL, From, user_info=user)
    return PlainTextResponse("\n".join(responses))
