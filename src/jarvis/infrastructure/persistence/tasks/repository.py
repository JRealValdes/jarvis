"""SQLite repository for periodic task definitions and run metadata."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from jarvis.core.paths import TASKS_DB_PATH
from jarvis.domain.tasks.schedule import (
    compute_next_run_at,
    validate_schedule,
    validate_timezone,
)

DB_PATH = str(TASKS_DB_PATH)

NOTIFY_POLICIES = frozenset({"always", "never", "on_change"})
RUN_STATUSES = frozenset({"running", "succeeded", "failed"})


@dataclass(frozen=True)
class TaskDefinitionRecord:
    """Durable periodic task definition."""

    id: str
    owner_real_name: str
    title: str
    instruction: str
    schedule: dict[str, Any]
    timezone: str
    notify_policy: str
    enabled: bool
    next_run_at: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class TaskRunRecord:
    """Durable metadata for one scheduled (or manual) task run."""

    id: str
    task_id: str
    started_at: str
    finished_at: str | None
    status: str
    summary: str | None
    push_sent: bool
    error: str | None


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def init_tasks_db() -> None:
    """
    Create the tasks database and tables if they do not exist.

    Returns:
        None.
    """
    TASKS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS task_definitions (
                id TEXT PRIMARY KEY,
                owner_real_name TEXT NOT NULL,
                title TEXT NOT NULL,
                instruction TEXT NOT NULL,
                schedule_json TEXT NOT NULL,
                timezone TEXT NOT NULL,
                notify_policy TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1,
                next_run_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS task_runs (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                status TEXT NOT NULL,
                summary TEXT,
                push_sent INTEGER NOT NULL DEFAULT 0,
                error TEXT,
                FOREIGN KEY (task_id) REFERENCES task_definitions(id)
                    ON DELETE CASCADE
            )
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_task_definitions_owner "
            "ON task_definitions(owner_real_name)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_task_definitions_due "
            "ON task_definitions(enabled, next_run_at)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_task_runs_task "
            "ON task_runs(task_id, started_at DESC)"
        )
        conn.commit()


def _row_to_definition(row: sqlite3.Row) -> TaskDefinitionRecord:
    """Map a SQLite row to a TaskDefinitionRecord."""
    return TaskDefinitionRecord(
        id=row["id"],
        owner_real_name=row["owner_real_name"],
        title=row["title"],
        instruction=row["instruction"],
        schedule=json.loads(row["schedule_json"]),
        timezone=row["timezone"],
        notify_policy=row["notify_policy"],
        enabled=bool(row["enabled"]),
        next_run_at=row["next_run_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_run(row: sqlite3.Row) -> TaskRunRecord:
    """Map a SQLite row to a TaskRunRecord."""
    return TaskRunRecord(
        id=row["id"],
        task_id=row["task_id"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        status=row["status"],
        summary=row["summary"],
        push_sent=bool(row["push_sent"]),
        error=row["error"],
    )


def create_task(
    *,
    owner_real_name: str,
    title: str,
    instruction: str,
    schedule: dict[str, Any],
    timezone_name: str,
    notify_policy: str = "always",
    enabled: bool = True,
) -> TaskDefinitionRecord:
    """
    Insert a new task definition for ``owner_real_name``.

    Args:
        owner_real_name: JWT ``real_name`` of the owner.
        title: Short label for list UIs.
        instruction: Goal / prompt for each scheduled run.
        schedule: Raw schedule mapping (validated).
        timezone_name: IANA timezone for the schedule.
        notify_policy: ``always``, ``never``, or ``on_change``.
        enabled: Whether the scheduler should fire this task.

    Returns:
        The created definition.

    Raises:
        ValueError: On invalid schedule, timezone, or notify policy.
    """
    normalized = validate_schedule(schedule)
    tz = validate_timezone(timezone_name)
    policy = (notify_policy or "always").strip().lower()
    if policy not in NOTIFY_POLICIES:
        raise ValueError(
            f"notify_policy must be one of: {', '.join(sorted(NOTIFY_POLICIES))}"
        )
    title_clean = (title or "").strip()
    instruction_clean = (instruction or "").strip()
    if not title_clean:
        raise ValueError("title cannot be empty.")
    if not instruction_clean:
        raise ValueError("instruction cannot be empty.")
    owner = (owner_real_name or "").strip()
    if not owner:
        raise ValueError("owner_real_name cannot be empty.")
    now = _utc_now_iso()
    next_run = (
        compute_next_run_at(normalized, tz).replace(microsecond=0).isoformat()
        if enabled
        else None
    )
    task_id = str(uuid.uuid4())
    init_tasks_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            INSERT INTO task_definitions (
                id, owner_real_name, title, instruction, schedule_json,
                timezone, notify_policy, enabled, next_run_at,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                owner,
                title_clean,
                instruction_clean,
                json.dumps(normalized),
                tz,
                policy,
                int(enabled),
                next_run,
                now,
                now,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM task_definitions WHERE id = ?", (task_id,)
        ).fetchone()
    assert row is not None
    return _row_to_definition(row)


def update_task(
    task_id: str,
    owner_real_name: str,
    *,
    title: str | None = None,
    instruction: str | None = None,
    schedule: dict[str, Any] | None = None,
    timezone_name: str | None = None,
    notify_policy: str | None = None,
    enabled: bool | None = None,
) -> TaskDefinitionRecord:
    """
    Update fields on an owned task definition.

    Args:
        task_id: Task to update.
        owner_real_name: Must match the owner.
        title: Optional new title.
        instruction: Optional new instruction.
        schedule: Optional new schedule.
        timezone_name: Optional new timezone.
        notify_policy: Optional new notify policy.
        enabled: Optional enabled flag.

    Returns:
        Updated definition.

    Raises:
        LookupError: If the task is missing or not owned by the user.
        ValueError: On invalid field values.
    """
    existing = get_task_for_owner(task_id, owner_real_name)
    if existing is None:
        raise LookupError("Task not found.")
    new_title = existing.title if title is None else title.strip()
    new_instruction = (
        existing.instruction if instruction is None else instruction.strip()
    )
    new_schedule = (
        existing.schedule if schedule is None else validate_schedule(schedule)
    )
    new_tz = (
        existing.timezone
        if timezone_name is None
        else validate_timezone(timezone_name)
    )
    new_policy = existing.notify_policy
    if notify_policy is not None:
        new_policy = notify_policy.strip().lower()
        if new_policy not in NOTIFY_POLICIES:
            raise ValueError(
                f"notify_policy must be one of: {', '.join(sorted(NOTIFY_POLICIES))}"
            )
    new_enabled = existing.enabled if enabled is None else bool(enabled)
    if not new_title:
        raise ValueError("title cannot be empty.")
    if not new_instruction:
        raise ValueError("instruction cannot be empty.")
    next_run = (
        compute_next_run_at(new_schedule, new_tz).replace(microsecond=0).isoformat()
        if new_enabled
        else None
    )
    now = _utc_now_iso()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            UPDATE task_definitions SET
                title = ?, instruction = ?, schedule_json = ?, timezone = ?,
                notify_policy = ?, enabled = ?, next_run_at = ?, updated_at = ?
            WHERE id = ? AND owner_real_name = ?
            """,
            (
                new_title,
                new_instruction,
                json.dumps(new_schedule),
                new_tz,
                new_policy,
                int(new_enabled),
                next_run,
                now,
                task_id,
                owner_real_name,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM task_definitions WHERE id = ?", (task_id,)
        ).fetchone()
    assert row is not None
    return _row_to_definition(row)


def delete_task(task_id: str, owner_real_name: str) -> bool:
    """
    Delete an owned task and its runs.

    Args:
        task_id: Task to delete.
        owner_real_name: Must match the owner.

    Returns:
        True if a row was deleted.
    """
    init_tasks_db()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "DELETE FROM task_definitions WHERE id = ? AND owner_real_name = ?",
            (task_id, owner_real_name),
        )
        conn.execute("DELETE FROM task_runs WHERE task_id = ?", (task_id,))
        conn.commit()
        return cursor.rowcount > 0


def get_task(task_id: str) -> TaskDefinitionRecord | None:
    """
    Load a task by id (any owner).

    Args:
        task_id: Task id.

    Returns:
        Definition or None.
    """
    init_tasks_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM task_definitions WHERE id = ?", (task_id,)
        ).fetchone()
    return _row_to_definition(row) if row else None


def get_task_for_owner(
    task_id: str, owner_real_name: str
) -> TaskDefinitionRecord | None:
    """
    Load a task only when owned by ``owner_real_name``.

    Args:
        task_id: Task id.
        owner_real_name: Expected owner.

    Returns:
        Definition or None.
    """
    task = get_task(task_id)
    if task is None or task.owner_real_name != owner_real_name:
        return None
    return task


def list_tasks_for_owner(owner_real_name: str) -> list[TaskDefinitionRecord]:
    """
    List all tasks for an owner, newest first.

    Args:
        owner_real_name: JWT ``real_name``.

    Returns:
        Task definitions.
    """
    init_tasks_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT * FROM task_definitions
            WHERE owner_real_name = ?
            ORDER BY created_at DESC
            """,
            (owner_real_name,),
        ).fetchall()
    return [_row_to_definition(row) for row in rows]


def list_tasks_due(now_iso: str | None = None) -> list[TaskDefinitionRecord]:
    """
    List enabled tasks whose ``next_run_at`` is due.

    Args:
        now_iso: Comparison instant (defaults to UTC now).

    Returns:
        Due task definitions.
    """
    init_tasks_db()
    now = now_iso or _utc_now_iso()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT * FROM task_definitions
            WHERE enabled = 1
              AND next_run_at IS NOT NULL
              AND next_run_at <= ?
            ORDER BY next_run_at ASC
            """,
            (now,),
        ).fetchall()
    return [_row_to_definition(row) for row in rows]


def set_next_run_at(task_id: str, next_run_at: str | None) -> None:
    """
    Persist the next scheduled run instant for a task.

    Args:
        task_id: Task id.
        next_run_at: ISO-8601 UTC instant, or None when disabled.

    Returns:
        None.
    """
    init_tasks_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE task_definitions
            SET next_run_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (next_run_at, _utc_now_iso(), task_id),
        )
        conn.commit()


def record_run(
    *,
    task_id: str,
    status: str,
    summary: str | None = None,
    error: str | None = None,
    push_sent: bool = False,
    started_at: str | None = None,
    finished_at: str | None = None,
    run_id: str | None = None,
) -> TaskRunRecord:
    """
    Insert a finished (or in-progress) run row.

    Args:
        task_id: Parent task.
        status: ``running``, ``succeeded``, or ``failed``.
        summary: Short summary for list UIs.
        error: Error detail when failed.
        push_sent: Whether a push was delivered for this run.
        started_at: Optional start instant.
        finished_at: Optional finish instant.
        run_id: Optional pre-allocated id.

    Returns:
        The stored run record.

    Raises:
        ValueError: If ``status`` is invalid.
    """
    if status not in RUN_STATUSES:
        raise ValueError(f"Invalid run status: {status}")
    init_tasks_db()
    rid = run_id or str(uuid.uuid4())
    started = started_at or _utc_now_iso()
    finished = finished_at
    if status != "running" and finished is None:
        finished = _utc_now_iso()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(
            """
            INSERT INTO task_runs (
                id, task_id, started_at, finished_at, status,
                summary, push_sent, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rid,
                task_id,
                started,
                finished,
                status,
                summary,
                int(push_sent),
                error,
            ),
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM task_runs WHERE id = ?", (rid,)
        ).fetchone()
    assert row is not None
    return _row_to_run(row)


def update_run(
    run_id: str,
    *,
    status: str | None = None,
    summary: str | None = None,
    error: str | None = None,
    push_sent: bool | None = None,
    finished_at: str | None = None,
) -> TaskRunRecord | None:
    """
    Patch fields on an existing run.

    Args:
        run_id: Run to update.
        status: Optional new status.
        summary: Optional summary.
        error: Optional error text.
        push_sent: Optional push flag.
        finished_at: Optional finish instant.

    Returns:
        Updated run, or None if missing.
    """
    init_tasks_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM task_runs WHERE id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return None
        new_status = status if status is not None else row["status"]
        if new_status not in RUN_STATUSES:
            raise ValueError(f"Invalid run status: {new_status}")
        new_summary = summary if summary is not None else row["summary"]
        new_error = error if error is not None else row["error"]
        new_push = (
            int(push_sent) if push_sent is not None else row["push_sent"]
        )
        new_finished = finished_at
        if new_finished is None and new_status != "running":
            new_finished = row["finished_at"] or _utc_now_iso()
        elif new_finished is None:
            new_finished = row["finished_at"]
        conn.execute(
            """
            UPDATE task_runs SET
                status = ?, summary = ?, error = ?, push_sent = ?,
                finished_at = ?
            WHERE id = ?
            """,
            (new_status, new_summary, new_error, new_push, new_finished, run_id),
        )
        conn.commit()
        updated = conn.execute(
            "SELECT * FROM task_runs WHERE id = ?", (run_id,)
        ).fetchone()
    assert updated is not None
    return _row_to_run(updated)


def list_runs_for_task(
    task_id: str, *, limit: int = 20
) -> list[TaskRunRecord]:
    """
    List recent runs for a task (newest first).

    Args:
        task_id: Parent task.
        limit: Max rows to return.

    Returns:
        Run records.
    """
    init_tasks_db()
    capped = max(1, min(int(limit), 100))
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT * FROM task_runs
            WHERE task_id = ?
            ORDER BY started_at DESC
            LIMIT ?
            """,
            (task_id, capped),
        ).fetchall()
    return [_row_to_run(row) for row in rows]


def latest_run_for_task(task_id: str) -> TaskRunRecord | None:
    """
    Return the most recent run for a task, if any.

    Args:
        task_id: Parent task.

    Returns:
        Latest run or None.
    """
    runs = list_runs_for_task(task_id, limit=1)
    return runs[0] if runs else None
