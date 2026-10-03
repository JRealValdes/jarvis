"""Pydantic schemas for chat and session management."""

from typing import Optional

from pydantic import BaseModel, Field

from jarvis.core.config import DEFAULT_MODEL


class AskInput(BaseModel):
    """JSON body for POST /ask."""

    message: str = Field(description="User message for Jarvis.")
    model_name: str = Field(
        default=DEFAULT_MODEL.name,
        description="ModelEnum member name (e.g. GPT_4O_MINI).",
    )
    thread_id: str | None = Field(
        default=None,
        description="Conversation thread; defaults to JWT real_name.",
    )


class ThreadIdPayload(BaseModel):
    """Optional body for POST /reset-session."""

    thread_id: Optional[str] = Field(
        default=None,
        description="Thread to reset; only admins may target another user.",
    )
