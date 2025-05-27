from langchain.tools import tool
from langchain.tools.base import ToolException
from langchain.callbacks.manager import CallbackManagerForToolRun
from typing import Optional
from pydantic import BaseModel
from openai import OpenAI
import os

class TranscribeAudioInput(BaseModel):
    """Parameters required to transcribe an audio file"""
    file_path: str

@tool("transcribe_audio", args_schema=TranscribeAudioInput)
def speech_to_text_tool(
    file_path: str,
    run_manager: Optional[CallbackManagerForToolRun] = None,
) -> str:
    """
    Transcribes an audio file (.mp3, .wav, etc.) using OpenAI Audio Transcriptions and returns the transcribed text.
    You must provide the full path to the audio file in file_path.
    """

    if not os.path.exists(file_path):
        raise ToolException(f"The file does not exist at the provided path: {file_path}")
    
    try:
        with open(file_path, "rb") as audio_file:
            transcription = OpenAI().audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file
            )
        return transcription.text
    except Exception as e:
        raise ToolException(f"Failed to transcribe the audio file: {str(e)}")
