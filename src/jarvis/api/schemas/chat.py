"""Pydantic schemas for chat and session management."""

from typing import Optional

from pydantic import BaseModel, Field

from jarvis.core.config import DEFAULT_MODEL


class ImageAttachment(BaseModel):
    """One image attached to POST /ask."""

    media_type: str = Field(
        description="image/jpeg, image/png, image/gif, or image/webp.",
    )
    data_base64: str = Field(
        description="Raw base64 image bytes, or a data: URL.",
    )


class AskInput(BaseModel):
    """JSON body for POST /ask."""

    message: str = Field(
        default="",
        description="User message for Jarvis. May be empty when images are attached.",
    )
    images: list[ImageAttachment] = Field(
        default_factory=list,
        description="Up to 4 images for this turn (vision models only).",
    )
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
