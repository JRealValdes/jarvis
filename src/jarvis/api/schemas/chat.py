"""Pydantic schemas for chat and session management."""

from typing import Optional

from pydantic import BaseModel, Field

from jarvis.core.config import DEFAULT_MODEL


class AskInput(BaseModel):
    """JSON body for POST /ask."""

    message: str = Field(description="Mensaje del usuario para Jarvis.")
    model_name: str = Field(
        default=DEFAULT_MODEL.name,
        description="Nombre del miembro ModelEnum (ej. GPT_3_5).",
    )
    thread_id: str | None = Field(
        default=None,
        description="Hilo de conversación; por defecto real_name del JWT.",
    )


class ThreadIdPayload(BaseModel):
    """Optional body for POST /reset-session."""

    thread_id: Optional[str] = Field(
        default=None,
        description="Hilo a reiniciar; solo admins pueden indicar otro usuario.",
    )
