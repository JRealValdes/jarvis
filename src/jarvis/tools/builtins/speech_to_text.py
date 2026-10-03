"""Audio transcription with OpenAI Whisper for the agent and Gradio UI."""

import os
from typing import Optional

from langchain_core.tools import tool, ToolException
from langchain_core.callbacks.manager import CallbackManagerForToolRun
from openai import OpenAI
from pydantic import BaseModel, Field


class TranscribeAudioInput(BaseModel):
    """Argument schema for the transcription tool."""

    file_path: str = Field(description="Absolute or relative path to the audio file.")


@tool("transcribe_audio", args_schema=TranscribeAudioInput)
def speech_to_text_tool(
    file_path: str,
    run_manager: Optional[CallbackManagerForToolRun] = None,
) -> str:
    """
    Transcribe an audio file (.mp3, .wav, etc.) with OpenAI Whisper.

    Args:
        file_path: Path to the audio file on disk.
        run_manager: Optional LangChain callback manager.

    Returns:
        Transcribed text.

    Raises:
        ToolException: If the file does not exist or the OpenAI API fails.
    """
    if not os.path.exists(file_path):
        raise ToolException(f"The file does not exist at the provided path: {file_path}")

    try:
        with open(file_path, "rb") as audio_file:
            transcription = OpenAI().audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
            )
        return transcription.text
    except Exception as e:
        raise ToolException(f"Failed to transcribe the audio file: {str(e)}") from e
