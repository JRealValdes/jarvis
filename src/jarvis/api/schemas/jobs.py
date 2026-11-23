"""Pydantic schemas for async chat jobs."""

from __future__ import annotations

from pydantic import BaseModel, Field

from jarvis.api.schemas.chat import ImageAttachment


class AsyncAskInput(BaseModel):
    """Submit a chat turn that completes asynchronously."""

    message: str = ""
    images: list[ImageAttachment] = Field(default_factory=list)
    model_name: str = "GPT_4O_MINI"
    thread_id: str | None = None


class JobAcceptedOut(BaseModel):
    """Immediate response after accepting an async ask."""

    job_id: str
    status: str
    thread_id: str


class JobStatusOut(BaseModel):
    """Pollable job status."""

    job_id: str
    status: str
    thread_id: str
    response: list[str] | None = None
    error: str | None = None
    created_at: str
    updated_at: str
    finished_at: str | None = None
