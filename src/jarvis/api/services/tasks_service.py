"""Periodic task use cases for the HTTP API."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from jarvis.api.schemas.tasks import (
    TaskCreateInput,
    TaskOut,
    TaskRunOut,
    TaskUpdateInput,
)
from jarvis.domain.tasks.thread_ids import task_chat_thread_id
from jarvis.infrastructure.persistence.tasks.repository import (
    TaskDefinitionRecord,
    TaskRunRecord,
    create_task,
    delete_task,
    get_task_for_owner,
    latest_run_for_task,
    list_runs_for_task,
    list_tasks_for_owner,
    update_task,
)
from jarvis.infrastructure.tasks.runner import execute_task_run


def _banner(next_reset_at: str | None) -> str:
    """English banner copy for the ephemeral task chat."""
    if not next_reset_at:
        return "This conversation resets on the next scheduled run."
    return (
        f"This conversation resets at the next scheduled run ({next_reset_at})."
    )


def _run_out(run: TaskRunRecord) -> TaskRunOut:
    """Map a run record to the API schema."""
    return TaskRunOut(
        id=run.id,
        task_id=run.task_id,
        started_at=run.started_at,
        finished_at=run.finished_at,
        status=run.status,
        summary=run.summary,
        push_sent=run.push_sent,
        error=run.error,
    )


def _task_out(task: TaskDefinitionRecord) -> TaskOut:
    """Map a definition (+ latest run) to the API schema."""
    latest = latest_run_for_task(task.id)
    next_reset = task.next_run_at
    return TaskOut(
        id=task.id,
        title=task.title,
        instruction=task.instruction,
        schedule=task.schedule,
        timezone=task.timezone,
        notify_policy=task.notify_policy,
        enabled=task.enabled,
        next_run_at=task.next_run_at,
        next_reset_at=next_reset,
        next_reset_banner=_banner(next_reset),
        thread_id=task_chat_thread_id(task.id),
        created_at=task.created_at,
        updated_at=task.updated_at,
        latest_run=_run_out(latest) if latest else None,
    )


class TasksService:
    """Owner-scoped CRUD and run triggers for periodic tasks."""

    def list_tasks(self, user: dict[str, Any]) -> list[TaskOut]:
        """
        List tasks for the authenticated user.

        Args:
            user: JWT claims.

        Returns:
            Task list items.
        """
        return [_task_out(task) for task in list_tasks_for_owner(user["real_name"])]

    def get_task(self, task_id: str, user: dict[str, Any]) -> TaskOut:
        """
        Return one owned task.

        Args:
            task_id: Task id.
            user: JWT claims.

        Returns:
            Task detail.

        Raises:
            HTTPException: 404 when missing.
        """
        task = get_task_for_owner(task_id, user["real_name"])
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found.")
        return _task_out(task)

    def create(self, body: TaskCreateInput, user: dict[str, Any]) -> TaskOut:
        """
        Create a task for the authenticated user.

        Args:
            body: Create payload.
            user: JWT claims.

        Returns:
            Created task.

        Raises:
            HTTPException: 400 on validation errors.
        """
        try:
            task = create_task(
                owner_real_name=user["real_name"],
                title=body.title,
                instruction=body.instruction,
                schedule=body.schedule.model_dump(),
                timezone_name=body.timezone,
                notify_policy=body.notify_policy,
                enabled=body.enabled,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _task_out(task)

    def update(
        self, task_id: str, body: TaskUpdateInput, user: dict[str, Any]
    ) -> TaskOut:
        """
        Update an owned task.

        Args:
            task_id: Task id.
            body: Partial update.
            user: JWT claims.

        Returns:
            Updated task.

        Raises:
            HTTPException: 404 / 400.
        """
        try:
            task = update_task(
                task_id,
                user["real_name"],
                title=body.title,
                instruction=body.instruction,
                schedule=(
                    body.schedule.model_dump() if body.schedule is not None else None
                ),
                timezone_name=body.timezone,
                notify_policy=body.notify_policy,
                enabled=body.enabled,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail="Task not found.") from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _task_out(task)

    def delete(self, task_id: str, user: dict[str, Any]) -> dict[str, str]:
        """
        Delete an owned task.

        Args:
            task_id: Task id.
            user: JWT claims.

        Returns:
            Status dict.

        Raises:
            HTTPException: 404 when missing.
        """
        if not delete_task(task_id, user["real_name"]):
            raise HTTPException(status_code=404, detail="Task not found.")
        return {"status": "ok", "message": "Task deleted"}

    def list_runs(
        self, task_id: str, user: dict[str, Any], *, limit: int = 20
    ) -> list[TaskRunOut]:
        """
        List recent runs for an owned task.

        Args:
            task_id: Task id.
            user: JWT claims.
            limit: Max rows.

        Returns:
            Run metadata list.

        Raises:
            HTTPException: 404 when the task is missing.
        """
        task = get_task_for_owner(task_id, user["real_name"])
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found.")
        return [_run_out(run) for run in list_runs_for_task(task_id, limit=limit)]

    async def run_now(self, task_id: str, user: dict[str, Any]) -> TaskRunOut:
        """
        Trigger an immediate run (still advances ``next_run_at``).

        Args:
            task_id: Task id.
            user: JWT claims.

        Returns:
            Finished run metadata.

        Raises:
            HTTPException: 404 when missing.
        """
        task = get_task_for_owner(task_id, user["real_name"])
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found.")
        run = await execute_task_run(task, advance_schedule=True, send_push=True)
        return _run_out(run)


tasks_service = TasksService()
