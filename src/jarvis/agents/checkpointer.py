"""SQLite checkpointers for Jarvis conversation threads.

Each model has its own file under ``data/checkpoints``. The file outlives the
process, so a restart keeps the thread. Global cache reset deletes the files.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from jarvis.core.enums import ModelEnum
from jarvis.core.paths import DATA_DIR

CHECKPOINTS_DIR: Path = DATA_DIR / "checkpoints"
"""Directory of per-model SQLite checkpoint files. Tests may replace this."""


def checkpoint_path(model: ModelEnum) -> Path:
    """
    Return the checkpoint file for a model.

    Args:
        model: Model whose threads are stored in the file.

    Returns:
        Path ending in ``{model.name}.sqlite``.
    """
    return CHECKPOINTS_DIR / f"{model.name}.sqlite"


@dataclass
class SqliteCheckpoint:
    """Open SQLite connection and the LangGraph saver that uses it."""

    path: Path
    connection: sqlite3.Connection
    saver: SqliteSaver

    def close(self) -> None:
        """Close the SQLite connection."""
        self.connection.close()


def open_checkpointer(path: Path) -> SqliteCheckpoint:
    """
    Open a SQLite checkpointer at ``path``, creating parent directories.

    Args:
        path: Database file. Created on first setup.

    Returns:
        Connection and saver. Caller must ``close`` the connection.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), check_same_thread=False)
    saver = SqliteSaver(connection)
    saver.setup()
    return SqliteCheckpoint(path=path, connection=connection, saver=saver)


def open_model_checkpointer(model: ModelEnum) -> SqliteCheckpoint:
    """
    Open the checkpointer file for ``model``.

    Args:
        model: Model whose thread store should be opened.

    Returns:
        Open checkpoint handle.
    """
    return open_checkpointer(checkpoint_path(model))


def delete_persisted_thread(model: ModelEnum, thread_id: str) -> None:
    """
    Delete one thread from disk when no live agent holds the file.

    Args:
        model: Model file to update.
        thread_id: Conversation id to remove.

    Returns:
        None. No-op when the model has no checkpoint file yet.
    """
    path = checkpoint_path(model)
    if not path.exists():
        return
    opened = open_checkpointer(path)
    try:
        opened.saver.delete_thread(thread_id)
    finally:
        opened.close()


def clear_all_checkpoints() -> None:
    """
    Delete every file in the checkpoint directory.

    Returns:
        None. No-op when the directory does not exist.

    Raises:
        OSError: If a file cannot be removed.
    """
    if not CHECKPOINTS_DIR.exists():
        return
    for path in CHECKPOINTS_DIR.iterdir():
        if path.is_file():
            path.unlink()
