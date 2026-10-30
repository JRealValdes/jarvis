"""Chat, session, and history use cases."""

from fastapi import HTTPException

from jarvis.agents.session import (
    ask_jarvis,
    check_individual_session_cache_exists,
    get_message_history,
    reset_session,
)
from jarvis.api.errors import ForbiddenError
from jarvis.api.schemas.chat import AskInput, ThreadIdPayload
from jarvis.core.enums import ModelEnum
from jarvis.infrastructure.images import ImageAttachmentError, VisionNotSupportedError
from jarvis.infrastructure.images.store import absolutize_stored_image_urls


class ChatService:
    """Orchestrates Jarvis conversations via the API."""

    async def ask(self, input_data: AskInput, user: dict, *, origin: str = "") -> dict:
        """
        Send a message to Jarvis on the API event loop.

        Args:
            input_data: Message, optional images, model, and optional thread_id.
            user: Decoded JWT claims.
            origin: Scheme, host, and port the client used for this request.

        Returns:
            Dict ``{response: list[str]}``. Stored image paths use ``origin``.

        Raises:
            HTTPException: 400 when the turn is empty or an image is rejected.
        """
        message = input_data.message or ""
        if not message.strip() and not input_data.images:
            raise HTTPException(status_code=400, detail="Message cannot be empty.")
        model_enum = ModelEnum[input_data.model_name]
        thread_id = input_data.thread_id or user["real_name"]
        images = [item.model_dump() for item in input_data.images]
        try:
            answer = await ask_jarvis(
                message,
                model_enum,
                thread_id,
                user_info=user,
                images=images or None,
            )
        except (ImageAttachmentError, VisionNotSupportedError) as exc:
            raise HTTPException(status_code=400, detail=exc.message) from exc
        return {
            "response": [
                absolutize_stored_image_urls(item, origin)
                if isinstance(item, str)
                else item
                for item in answer
            ]
        }

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
            ForbiddenError: If a non-admin resets another thread.
        """
        thread_id = payload.thread_id if payload else None
        thread_id = self._resolve_thread_id(thread_id, user, action="reset")
        reset_session(thread_id)
        return {"status": "ok", "message": "Memory reset"}

    def individual_cache_exists(self, real_name: str) -> bool:
        """
        Report whether a session is cached for a real_name.

        Args:
            real_name: User identifier.

        Returns:
            True if a session cache entry exists.
        """
        return check_individual_session_cache_exists(real_name)

    def get_history(
        self, thread_id: str | None, user: dict, *, origin: str = ""
    ) -> dict:
        """
        Return parsed message history for a thread.

        Args:
            thread_id: Explicit thread or None to use JWT real_name.
            user: Decoded JWT claims.
            origin: Scheme, host, and port the client used for this request.

        Returns:
            Dict ``{thread_id, messages}``. Stored image paths use ``origin``.

        Raises:
            ForbiddenError: If a non-admin queries another thread.
        """
        thread_id = self._resolve_thread_id(thread_id, user, action="read")
        history = get_message_history(thread_id)
        messages = []
        for item in history:
            if isinstance(item, dict) and isinstance(item.get("content"), str):
                copied = dict(item)
                copied["content"] = absolutize_stored_image_urls(
                    item["content"], origin
                )
                messages.append(copied)
            else:
                messages.append(item)
        return {"thread_id": thread_id, "messages": messages}

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
            ForbiddenError: If a non-admin accesses another thread.
        """
        if thread_id:
            if not user.get("admin", False):
                if action == "reset":
                    detail = (
                        "You do not have permission to reset other users' memory."
                    )
                else:
                    detail = (
                        "You do not have permission to view other users' history."
                    )
                raise ForbiddenError(detail)
            return thread_id
        return user["real_name"]


chat_service = ChatService()
