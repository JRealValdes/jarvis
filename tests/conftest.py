"""Shared pytest fixtures and environment for Jarvis tests."""

import os

import pytest
from cryptography.fernet import Fernet


@pytest.fixture(scope="session", autouse=True)
def _test_env():
    """Minimal env so imports (security, API) do not fail in CI/local pytest."""
    os.environ.setdefault("JWT_SECRET_KEY", "pytest-jwt-secret-do-not-use-in-production")
    os.environ.setdefault("FERNET_KEY", Fernet.generate_key().decode())
    yield
