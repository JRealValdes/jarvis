"""Audio transcription with OpenAI Whisper for the agent and Gradio UI."""

from typing import Optional

from langchain_core.callbacks.manager import CallbackManagerForToolRun
from langchain_core.tools import ToolException, tool
from pydantic import BaseModel, Field

from jarvis.infrastructure.audio import AudioTranscriptionError, transcribe_audio_path


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
    try:
        return transcribe_audio_path(file_path)
    except AudioTranscriptionError as exc:
        raise ToolException(exc.message) from exc
