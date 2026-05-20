"""Casos de uso de chat, sesión e historial."""

from fastapi import HTTPException, status

from agents.session import (
    ask_jarvis,
    check_individual_session_cache_exists,
    get_message_history,
    reset_session,
)
from api.schemas.chat import AskInput, ThreadIdPayload
from config import DEFAULT_MODEL
from enums.core_enums import ModelEnum


class ChatService:
    """Orquestación de conversaciones con Jarvis vía API."""

    def ask(self, input_data: AskInput, user: dict) -> dict:
        """
        Envía un mensaje a Jarvis.

        Args:
            input_data: Mensaje, modelo y thread_id opcional.
            user: Claims JWT.

        Returns:
            Dict ``{response: list[str]}``.
        """
        model_enum = ModelEnum[input_data.model_name]
        thread_id = input_data.thread_id or user["real_name"]
        answer = ask_jarvis(input_data.message, model_enum, thread_id, user_info=user)
        return {"response": answer}

    def reset_session_for_user(
        self, payload: ThreadIdPayload | None, user: dict
    ) -> dict:
        """
        Reinicia la caché de sesión del hilo indicado o del usuario actual.

        Args:
            payload: Cuerpo opcional con thread_id.
            user: Claims JWT.

        Returns:
            Dict ``{status, message}``.

        Raises:
            HTTPException: 403 si un no-admin resetea otro hilo.
        """
        thread_id = payload.thread_id if payload else None
        print(f"Realizando reset session con thread_id: {thread_id}")
        thread_id = self._resolve_thread_id(thread_id, user, action="reset")
        reset_session(thread_id)
        print(f"Limpieza exitosa del thread id: {thread_id}")
        return {"status": "ok", "message": "Memory reset"}

    def individual_cache_exists(self, real_name: str) -> bool:
        """
        Indica si hay sesión en caché para un real_name.

        Args:
            real_name: Identificador del usuario.

        Returns:
            True si existe entrada en caché de sesiones.
        """
        return check_individual_session_cache_exists(real_name)

    def get_history(self, thread_id: str | None, user: dict) -> dict:
        """
        Devuelve historial parseado de mensajes para un hilo.

        Args:
            thread_id: Hilo explícito o None para usar real_name del JWT.
            user: Claims JWT.

        Returns:
            Dict ``{thread_id, messages}``.

        Raises:
            HTTPException: 403 si un no-admin consulta otro hilo.
        """
        thread_id = self._resolve_thread_id(thread_id, user, action="read")
        history = get_message_history(thread_id)
        return {"thread_id": thread_id, "messages": history}

    def whatsapp_reply(self, body: str, sender_id: str, user: dict) -> str:
        """
        Procesa un mensaje WhatsApp y devuelve texto plano concatenado.

        Args:
            body: Texto del mensaje.
            sender_id: Identificador From (thread_id).
            user: Claims JWT.

        Returns:
            Respuestas de Jarvis unidas por saltos de línea.
        """
        responses = ask_jarvis(body, DEFAULT_MODEL, sender_id, user_info=user)
        return "\n".join(responses)

    def _resolve_thread_id(
        self, thread_id: str | None, user: dict, *, action: str
    ) -> str:
        """
        Resuelve thread_id y comprueba permisos de admin para hilos ajenos.

        Args:
            thread_id: Hilo solicitado o None.
            user: Claims JWT.
            action: ``reset`` o ``read`` (solo afecta el mensaje de error).

        Returns:
            thread_id efectivo.

        Raises:
            HTTPException: 403 si no-admin accede a otro hilo.
        """
        if thread_id:
            if not user.get("admin", False):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have permission to reset memory for other users.",
                )
            return thread_id
        return user["real_name"]


chat_service = ChatService()
