"""Chat, session, and history use cases."""

from fastapi import HTTPException, status

from jarvis.agents.session import (
    ask_jarvis,
    check_individual_session_cache_exists,
    get_message_history,
    reset_session,
)
from jarvis.api.schemas.chat import AskInput, ThreadIdPayload
from jarvis.core.enums import ModelEnum


class ChatService:
    """Orchestrates Jarvis conversations via the API."""

    def ask(self, input_data: AskInput, user: dict) -> dict:
        """
        Send a message to Jarvis.

        Args:
            input_data: Message, model, and optional thread_id.
            user: Decoded JWT claims.

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
        Reset session cache for the given thread or the current user.

        Args:
            payload: Optional body with thread_id.
            user: Decoded JWT claims.

        Returns:
            Dict ``{status, message}``.

        Raises:
            HTTPException: 403 if a non-admin resets another thread.
        """
        thread_id = payload.thread_id if payload else None
        thread_id = self._resolve_thread_id(thread_id, user, action="reset")
        reset_session(thread_id)
        return {"status": "ok", "message": "Memoria reiniciada"}

    def individual_cache_exists(self, real_name: str) -> bool:
        """
        Report whether a session is cached for a real_name.

        Args:
            real_name: User identifier.

        Returns:
            True if a session cache entry exists.
        """
        return check_individual_session_cache_exists(real_name)

    def get_history(self, thread_id: str | None, user: dict) -> dict:
        """
        Return parsed message history for a thread.

        Args:
            thread_id: Explicit thread or None to use JWT real_name.
            user: Decoded JWT claims.

        Returns:
            Dict ``{thread_id, messages}``.

        Raises:
            HTTPException: 403 if a non-admin queries another thread.
        """
        thread_id = self._resolve_thread_id(thread_id, user, action="read")
        history = get_message_history(thread_id)
        return {"thread_id": thread_id, "messages": history}

    def _resolve_thread_id(
        self, thread_id: str | None, user: dict, *, action: str
    ) -> str:
        """
        Resolve thread_id and enforce admin permissions for foreign threads.

        Args:
            thread_id: Requested thread or None.
            user: Decoded JWT claims.
            action: ``reset`` or ``read`` (only affects the error message).

        Returns:
            Effective thread_id.

        Raises:
            HTTPException: 403 if a non-admin accesses another thread.
        """
        if thread_id:
            if not user.get("admin", False):
                if action == "reset":
                    detail = (
                        "No tienes permiso para reiniciar la memoria de otros usuarios."
                    )
                else:
                    detail = (
                        "No tienes permiso para consultar el historial de otros usuarios."
                    )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=detail,
                )
            return thread_id
        return user["real_name"]


chat_service = ChatService()
