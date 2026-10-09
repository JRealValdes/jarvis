"""
Shared pytest fixtures for Jarvis.

Sets minimal environment variables before importing Fernet/JWT modules.
"""

import os
from pathlib import Path

import pytest
from cryptography.fernet import Fernet


@pytest.fixture(autouse=True)
def _isolate_checkpoints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep pytest from reading or deleting the developer's checkpoint files."""
    monkeypatch.setattr(
        "jarvis.agents.checkpointer.CHECKPOINTS_DIR",
        tmp_path / "checkpoints",
    )


@pytest.fixture(scope="session", autouse=True)
def _test_env():
    """Minimal env so imports (security, API) do not fail in CI/local pytest."""
    os.environ.setdefault("JWT_SECRET_KEY", "pytest-jwt-secret-do-not-use-in-production")
    os.environ.setdefault("FERNET_KEY", Fernet.generate_key().decode())
    yield
