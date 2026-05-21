"""Canonical filesystem paths for the Jarvis repository."""

from pathlib import Path


def find_project_root() -> Path:
    """
    Locate the repository root (directory that contains ``pyproject.toml``).

    Returns:
        Absolute path to the project root.

    Raises:
        RuntimeError: If no ``pyproject.toml`` is found in any parent directory.
    """
    current = Path(__file__).resolve().parent
    for directory in (current, *current.parents):
        if (directory / "pyproject.toml").is_file():
            return directory
    raise RuntimeError("No se encontró pyproject.toml en ningún directorio padre.")


PROJECT_ROOT: Path = find_project_root()
JARVIS_PACKAGE_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = PROJECT_ROOT / "data"
USERS_DB_PATH: Path = DATA_DIR / "users.db"
GOOGLE_CREDENTIALS_DIR: Path = JARVIS_PACKAGE_DIR / "api" / "google_api"
FIREBASE_PRIVATE_KEY_PATH: Path = PROJECT_ROOT / "api" / "firebase_project_secret_private_key.json"
MCP_DIR: Path = JARVIS_PACKAGE_DIR / "mcp"
MCP_SERVER_CONFIG_PATH: Path = MCP_DIR / "server_config.json"
