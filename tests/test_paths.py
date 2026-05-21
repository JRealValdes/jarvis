"""Tests for core.paths project root resolution."""

from pathlib import Path

from jarvis.core.paths import (
    DATA_DIR,
    FIREBASE_PRIVATE_KEY_PATH,
    GOOGLE_CREDENTIALS_DIR,
    MCP_SERVER_CONFIG_PATH,
    PROJECT_ROOT,
    USERS_DB_PATH,
)


def test_project_root_contains_pyproject():
    assert (PROJECT_ROOT / "pyproject.toml").is_file()


def test_data_paths_under_project_root():
    assert DATA_DIR == PROJECT_ROOT / "data"
    assert USERS_DB_PATH == DATA_DIR / "users.db"
    assert GOOGLE_CREDENTIALS_DIR == DATA_DIR / "google"
    assert FIREBASE_PRIVATE_KEY_PATH == DATA_DIR / "firebase_project_secret_private_key.json"
    assert MCP_SERVER_CONFIG_PATH == PROJECT_ROOT / "src" / "jarvis" / "mcp" / "server_config.json"
