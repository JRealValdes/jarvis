"""Audio transcription with OpenAI Whisper for the agent and Gradio UI."""

import os
from typing import Optional

from langchain_core.tools import tool, ToolException
from langchain_core.callbacks.manager import CallbackManagerForToolRun
from openai import OpenAI
from pydantic import BaseModel, Field


class TranscribeAudioInput(BaseModel):
    """Argument schema for the transcription tool."""

    file_path: str = Field(description="Ruta absoluta o relativa al archivo de audio.")


@tool("transcribe_audio", args_schema=TranscribeAudioInput)
def speech_to_text_tool(
    file_path: str,
    run_manager: Optional[CallbackManagerForToolRun] = None,
) -> str:
    """
    Transcribe un archivo de audio (.mp3, .wav, etc.) con OpenAI Whisper.

    Args:
        file_path: Ruta al archivo de audio en disco.
        run_manager: Callback manager de LangChain (opcional).

    Returns:
        Texto transcrito.

    Raises:
        ToolException: Si el archivo no existe o la API de OpenAI falla.
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
