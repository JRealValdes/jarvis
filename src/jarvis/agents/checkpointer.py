"""SQLite checkpointers for Jarvis conversation threads.

Each model has its own file under ``data/checkpoints``. The file outlives the
process, so a restart keeps the thread. Global cache reset deletes the files.

Live agents compile the graph with ``AsyncSqliteSaver`` because turns run
through ``graph.ainvoke``. Sync ``SqliteSaver`` remains for one-shot thread
deletes and tests that call ``graph.invoke``.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import aiosqlite
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

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


@dataclass
class AsyncSqliteCheckpoint:
    """Open aiosqlite connection and the async LangGraph saver that uses it."""

    path: Path
    connection: aiosqlite.Connection
    saver: AsyncSqliteSaver

    async def close(self) -> None:
        """Close the aiosqlite connection."""
        await self.connection.close()


async def aopen_checkpointer(path: Path) -> AsyncSqliteCheckpoint:
    """
    Open an async SQLite checkpointer at ``path``, creating parent directories.

    Must run on the event loop that will later ``ainvoke`` the graph.
    ``AsyncSqliteSaver`` binds its lock to that loop.

    Args:
        path: Database file. Created on first setup.

    Returns:
        Connection and saver. Caller must ``await close``.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = await aiosqlite.connect(str(path))
    saver = AsyncSqliteSaver(connection)
    await saver.setup()
    return AsyncSqliteCheckpoint(path=path, connection=connection, saver=saver)


async def aopen_model_checkpointer(model: ModelEnum) -> AsyncSqliteCheckpoint:
    """
    Open the async checkpointer file for ``model``.

    Args:
        model: Model whose thread store should be opened.

    Returns:
        Open async checkpoint handle.
    """
    return await aopen_checkpointer(checkpoint_path(model))


def delete_persisted_thread(model: ModelEnum, thread_id: str) -> None:
    """
    Delete one thread from the model's checkpoint file.

    Opens a short-lived sync connection. That still works while an async saver
    holds the same file, because both connections use WAL.

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
