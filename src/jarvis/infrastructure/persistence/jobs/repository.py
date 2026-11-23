"""SQLite store for asynchronous chat turn jobs."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from jarvis.core.paths import JOBS_DB_PATH

DB_PATH = str(JOBS_DB_PATH)
JOB_STATUSES = frozenset({"running", "done", "failed"})


@dataclass(frozen=True)
class ChatJobRecord:
    """One async chat turn."""

    id: str
    owner_real_name: str
    thread_id: str
    status: str
    response_json: str | None
    error: str | None
    created_at: str
    updated_at: str
    finished_at: str | None


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def init_jobs_db() -> None:
    """
    Create the jobs database and table if needed.

    Returns:
        None.
    """
    JOBS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_jobs (
                id TEXT PRIMARY KEY,
                owner_real_name TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                status TEXT NOT NULL,
                response_json TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                finished_at TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_jobs_owner "
            "ON chat_jobs(owner_real_name, created_at DESC)"
        )
        conn.commit()


def _row_to_job(row: sqlite3.Row) -> ChatJobRecord:
    """Map a SQLite row to ChatJobRecord."""
    return ChatJobRecord(
        id=row["id"],
        owner_real_name=row["owner_real_name"],
        thread_id=row["thread_id"],
        status=row["status"],
        response_json=row["response_json"],
        error=row["error"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        finished_at=row["finished_at"],
    )


def create_job(*, owner_real_name: str, thread_id: str) -> ChatJobRecord:
    """
    Insert a running job row.

    Args:
        owner_real_name: Job owner.
        thread_id: Conversation thread for the turn.

    Returns:
        Created job.
    """
    init_jobs_db()
    job_id = str(uuid.uuid4())
    now = _utc_now_iso()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            INSERT INTO chat_jobs (
                id, owner_real_name, thread_id, status, response_json,
                error, created_at, updated_at, finished_at
            ) VALUES (?, ?, ?, 'running', NULL, NULL, ?, ?, NULL)
            """,
            (job_id, owner_real_name, thread_id, now, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM chat_jobs WHERE id = ?", (job_id,)
        ).fetchone()
    assert row is not None
    return _row_to_job(row)


def update_job(
    job_id: str,
    *,
    status: str,
    response: list[str] | None = None,
    error: str | None = None,
) -> ChatJobRecord | None:
    """
    Mark a job done/failed and store the response.

    Args:
        job_id: Job id.
        status: ``done`` or ``failed`` (also allows ``running``).
        response: Assistant response fragments when done.
        error: Error text when failed.

    Returns:
        Updated job or None if missing.

    Raises:
        ValueError: On invalid status.
    """
    if status not in JOB_STATUSES:
        raise ValueError(f"Invalid job status: {status}")
    init_jobs_db()
    now = _utc_now_iso()
    finished = now if status in {"done", "failed"} else None
    response_json = json.dumps(response) if response is not None else None
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            UPDATE chat_jobs SET
                status = ?, response_json = ?, error = ?,
                updated_at = ?, finished_at = COALESCE(?, finished_at)
            WHERE id = ?
            """,
            (status, response_json, error, now, finished, job_id),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM chat_jobs WHERE id = ?", (job_id,)
        ).fetchone()
    return _row_to_job(row) if row else None


def get_job(job_id: str) -> ChatJobRecord | None:
    """
    Load a job by id.

    Args:
        job_id: Job id.

    Returns:
        Job or None.
    """
    init_jobs_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM chat_jobs WHERE id = ?", (job_id,)
        ).fetchone()
    return _row_to_job(row) if row else None


def get_job_for_owner(job_id: str, owner_real_name: str) -> ChatJobRecord | None:
    """
    Load a job only when owned by ``owner_real_name``.

    Args:
        job_id: Job id.
        owner_real_name: Expected owner.

    Returns:
        Job or None.
    """
    job = get_job(job_id)
    if job is None or job.owner_real_name != owner_real_name:
        return None
    return job
