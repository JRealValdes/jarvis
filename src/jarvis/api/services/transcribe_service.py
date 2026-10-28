"""HTTP speech-to-text use cases."""

from fastapi import HTTPException, UploadFile

from jarvis.infrastructure.audio import (
    AudioTranscriptionError,
    transcribe_audio_bytes,
)


class TranscribeService:
    """Transcribes uploaded audio via the shared Whisper helper."""

    async def transcribe_upload(self, file: UploadFile) -> dict[str, str]:
        """
        Read an uploaded audio part and return its transcription.

        Args:
            file: Multipart file part (field name ``file``).

        Returns:
            Dict ``{text: str}``.

        Raises:
            HTTPException: 400/413 for client errors; 502 if Whisper fails.
        """
        if file is None:
            raise HTTPException(status_code=400, detail="Missing audio file part 'file'.")

        data = await file.read()
        try:
            text = transcribe_audio_bytes(
                data,
                filename=file.filename or "",
                content_type=file.content_type,
            )
        except AudioTranscriptionError as exc:
            raise HTTPException(
                status_code=self._status_for(exc.code),
                detail=exc.message,
            ) from exc
        return {"text": text}

    @staticmethod
    def _status_for(code: str) -> int:
        """Map transcription error codes to HTTP status codes."""
        if code == "audio_too_large":
            return 413
        if code == "transcription_failed":
            return 502
        return 400


transcribe_service = TranscribeService()
