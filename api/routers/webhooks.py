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
    Twilio/WhatsApp webhook: forwards the message body to Jarvis.

    Args:
        request: FastAPI request (reserved for extensions).
        Body: Incoming message text.
        From: Sender identifier (used as thread_id).
        ProfileName: WhatsApp profile name (optional).
        user: JWT payload.

    Returns:
        PlainTextResponse with replies joined by newlines.
    """
    text = chat_service.whatsapp_reply(Body, From, user)
    return PlainTextResponse(text)
