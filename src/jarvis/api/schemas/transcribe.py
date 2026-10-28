"""Pydantic schemas for HTTP speech-to-text."""

from pydantic import BaseModel, Field


class TranscribeResponse(BaseModel):
    """JSON body returned by POST /transcribe."""

    text: str = Field(description="Whisper transcription of the uploaded audio.")
