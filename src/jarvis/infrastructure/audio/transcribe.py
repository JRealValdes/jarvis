"""OpenAI Whisper transcription shared by the agent tool and HTTP API."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from openai import OpenAI

# Align with OpenAI Whisper upload limit and jarvis_app attachment policy.
WHISPER_MODEL: str = "whisper-1"
MAX_AUDIO_UPLOAD_BYTES: int = 25 * 1024 * 1024
MAX_AUDIO_ATTACHMENTS_PER_TURN: int = 2

SUPPORTED_AUDIO_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".flac",
        ".m4a",
        ".mp3",
        ".mp4",
        ".mpeg",
        ".mpga",
        ".oga",
        ".ogg",
        ".wav",
        ".webm",
    }
)

SUPPORTED_AUDIO_CONTENT_TYPES: frozenset[str] = frozenset(
    {
        "audio/flac",
        "audio/mp4",
        "audio/m4a",
        "audio/mpeg",
        "audio/mp3",
        "audio/ogg",
        "audio/wav",
        "audio/wave",
        "audio/x-wav",
        "audio/webm",
        "video/mp4",
        "video/webm",
    }
)


class AudioTranscriptionError(Exception):
    """Raised when audio cannot be accepted or Whisper fails."""

    def __init__(self, message: str, *, code: str = "transcription_failed") -> None:
        super().__init__(message)
        self.message = message
        self.code = code


def _extension_for(filename: str) -> str:
    return Path(filename).suffix.lower()


def validate_audio_filename(filename: str | None) -> str:
    """
    Return a safe basename with a supported extension.

    Args:
        filename: Original upload or path name.

    Returns:
        Basename including a supported suffix.

    Raises:
        AudioTranscriptionError: If the name is missing or unsupported.
    """
    if not filename or not str(filename).strip():
        raise AudioTranscriptionError(
            "Audio filename is required.",
            code="missing_filename",
        )
    name = Path(filename).name
    ext = _extension_for(name)
    if ext not in SUPPORTED_AUDIO_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_AUDIO_EXTENSIONS))
        raise AudioTranscriptionError(
            f"Unsupported audio format '{ext or '(none)'}'. Allowed: {allowed}.",
            code="unsupported_format",
        )
    return name


def validate_audio_size(size_bytes: int) -> None:
    """
    Reject empty or oversized payloads.

    Args:
        size_bytes: Length of the audio bytes.

    Raises:
        AudioTranscriptionError: If empty or over ``MAX_AUDIO_UPLOAD_BYTES``.
    """
    if size_bytes <= 0:
        raise AudioTranscriptionError(
            "Audio file is empty.",
            code="empty_audio",
        )
    if size_bytes > MAX_AUDIO_UPLOAD_BYTES:
        raise AudioTranscriptionError(
            f"Audio exceeds max size of {MAX_AUDIO_UPLOAD_BYTES} bytes.",
            code="audio_too_large",
        )


def validate_content_type(content_type: str | None) -> None:
    """
    Optionally reject unknown Content-Type when the client sends one.

    Empty or ``application/octet-stream`` is allowed; extension still governs.

    Args:
        content_type: HTTP Content-Type or form part type.

    Raises:
        AudioTranscriptionError: If a specific type is present but not allowed.
    """
    if not content_type:
        return
    media = content_type.split(";")[0].strip().lower()
    if media in ("application/octet-stream", "binary/octet-stream"):
        return
    if media not in SUPPORTED_AUDIO_CONTENT_TYPES:
        raise AudioTranscriptionError(
            f"Unsupported audio Content-Type '{media}'.",
            code="unsupported_content_type",
        )


def transcribe_audio_path(file_path: str | Path) -> str:
    """
    Transcribe an audio file on disk with OpenAI Whisper.

    Args:
        file_path: Absolute or relative path to the audio file.

    Returns:
        Transcribed text.

    Raises:
        AudioTranscriptionError: If the file is missing, invalid, or Whisper fails.
    """
    path = Path(file_path)
    if not path.is_file():
        raise AudioTranscriptionError(
            f"The file does not exist at the provided path: {path}",
            code="file_not_found",
        )
    validate_audio_filename(path.name)
    size = path.stat().st_size
    validate_audio_size(size)
    try:
        with path.open("rb") as audio_file:
            transcription = OpenAI().audio.transcriptions.create(
                model=WHISPER_MODEL,
                file=audio_file,
            )
        return transcription.text
    except AudioTranscriptionError:
        raise
    except Exception as exc:
        raise AudioTranscriptionError(
            f"Failed to transcribe the audio file: {exc}",
            code="transcription_failed",
        ) from exc


def transcribe_audio_bytes(
    data: bytes,
    *,
    filename: str,
    content_type: str | None = None,
) -> str:
    """
    Validate in-memory audio, write a temp file, and transcribe with Whisper.

    The temp file is deleted after the call. Audio is not persisted.

    Args:
        data: Raw audio bytes.
        filename: Original filename (used for extension / Whisper name).
        content_type: Optional Content-Type from the upload.

    Returns:
        Transcribed text.

    Raises:
        AudioTranscriptionError: On validation or Whisper failure.
    """
    safe_name = validate_audio_filename(filename)
    validate_content_type(content_type)
    validate_audio_size(len(data))
    suffix = _extension_for(safe_name)
    fd, tmp_path = tempfile.mkstemp(prefix="jarvis_stt_", suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        return transcribe_audio_path(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
