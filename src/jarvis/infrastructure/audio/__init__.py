"""Audio helpers (transcription, caps shared with HTTP clients)."""

from jarvis.infrastructure.audio.transcribe import (
    MAX_AUDIO_ATTACHMENTS_PER_TURN,
    MAX_AUDIO_UPLOAD_BYTES,
    SUPPORTED_AUDIO_CONTENT_TYPES,
    SUPPORTED_AUDIO_EXTENSIONS,
    WHISPER_MODEL,
    AudioTranscriptionError,
    transcribe_audio_bytes,
    transcribe_audio_path,
)

__all__ = [
    "MAX_AUDIO_ATTACHMENTS_PER_TURN",
    "MAX_AUDIO_UPLOAD_BYTES",
    "SUPPORTED_AUDIO_CONTENT_TYPES",
    "SUPPORTED_AUDIO_EXTENSIONS",
    "WHISPER_MODEL",
    "AudioTranscriptionError",
    "transcribe_audio_bytes",
    "transcribe_audio_path",
]
