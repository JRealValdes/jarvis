"""Unit tests for Whisper transcription helpers and POST /transcribe."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock, patch

import jwt
import pytest
from fastapi.testclient import TestClient

from jarvis.api.app import app
from jarvis.core.config import JWT_ALGORITHM
from jarvis.infrastructure.audio import (
    MAX_AUDIO_UPLOAD_BYTES,
    AudioTranscriptionError,
    transcribe_audio_bytes,
)
from jarvis.infrastructure.audio.transcribe import (
    validate_audio_filename,
    validate_audio_size,
)


def _token(*, admin: bool = False) -> str:
    payload = {
        "sub": "pytest-user",
        "real_name": "Pytest User",
        "jarvis_name": "Sir",
        "is_female": False,
        "admin": admin,
        "exp": 9999999999,
    }
    secret = __import__("os").environ["JWT_SECRET_KEY"]
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def test_validate_audio_filename_rejects_missing() -> None:
    with pytest.raises(AudioTranscriptionError) as exc:
        validate_audio_filename("")
    assert exc.value.code == "missing_filename"


def test_validate_audio_filename_rejects_unsupported() -> None:
    with pytest.raises(AudioTranscriptionError) as exc:
        validate_audio_filename("clip.xyz")
    assert exc.value.code == "unsupported_format"


def test_validate_audio_filename_accepts_wav() -> None:
    assert validate_audio_filename("note.WAV") == "note.WAV"


def test_validate_audio_size_empty() -> None:
    with pytest.raises(AudioTranscriptionError) as exc:
        validate_audio_size(0)
    assert exc.value.code == "empty_audio"


def test_validate_audio_size_too_large() -> None:
    with pytest.raises(AudioTranscriptionError) as exc:
        validate_audio_size(MAX_AUDIO_UPLOAD_BYTES + 1)
    assert exc.value.code == "audio_too_large"


def test_transcribe_audio_bytes_happy_path() -> None:
    fake = MagicMock()
    fake.audio.transcriptions.create.return_value = MagicMock(text="hello world")
    with patch(
        "jarvis.infrastructure.audio.transcribe.OpenAI",
        return_value=fake,
    ):
        text = transcribe_audio_bytes(b"fake-audio", filename="clip.wav")
    assert text == "hello world"
    fake.audio.transcriptions.create.assert_called_once()


def test_transcribe_requires_auth() -> None:
    client = TestClient(app)
    response = client.post(
        "/transcribe",
        files={"file": ("clip.wav", b"abc", "audio/wav")},
    )
    assert response.status_code in (401, 403)


def test_transcribe_rejects_empty_file() -> None:
    client = TestClient(app)
    response = client.post(
        "/transcribe",
        headers={"Authorization": f"Bearer {_token()}"},
        files={"file": ("clip.wav", b"", "audio/wav")},
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_transcribe_rejects_unsupported_extension() -> None:
    client = TestClient(app)
    response = client.post(
        "/transcribe",
        headers={"Authorization": f"Bearer {_token()}"},
        files={"file": ("clip.txt", b"not-audio", "text/plain")},
    )
    assert response.status_code == 400
    assert "unsupported" in response.json()["detail"].lower()


def test_transcribe_happy_path_mocked() -> None:
    client = TestClient(app)
    with patch(
        "jarvis.api.services.transcribe_service.transcribe_audio_bytes",
        return_value="transcribed line",
    ):
        response = client.post(
            "/transcribe",
            headers={"Authorization": f"Bearer {_token()}"},
            files={"file": ("mic.m4a", b"fake-bytes", "audio/mp4")},
        )
    assert response.status_code == 200
    assert response.json() == {"text": "transcribed line"}


def test_transcribe_maps_too_large_to_413() -> None:
    client = TestClient(app)
    with patch(
        "jarvis.api.services.transcribe_service.transcribe_audio_bytes",
        side_effect=AudioTranscriptionError(
            f"Audio exceeds max size of {MAX_AUDIO_UPLOAD_BYTES} bytes.",
            code="audio_too_large",
        ),
    ):
        response = client.post(
            "/transcribe",
            headers={"Authorization": f"Bearer {_token()}"},
            files={"file": ("big.wav", BytesIO(b"x"), "audio/wav")},
        )
    assert response.status_code == 413
