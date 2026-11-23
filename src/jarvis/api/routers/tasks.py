"""HTTP routes for periodic task definitions and runs."""

from typing import Any

from fastapi import APIRouter, Depends, Query

from jarvis.api.dependencies import verify_jwt_token
from jarvis.api.schemas.tasks import (
    TaskCreateInput,
    TaskListOut,
    TaskOut,
    TaskRunOut,
    TaskRunsOut,
    TaskUpdateInput,
)
from jarvis.api.services.tasks_service import tasks_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=TaskListOut)
async def list_tasks(
    user: dict[str, Any] = Depends(verify_jwt_token),
) -> TaskListOut:
    """List periodic tasks for the authenticated user."""
    return TaskListOut(tasks=tasks_service.list_tasks(user))


@router.post("", response_model=TaskOut)
async def create_task(
    body: TaskCreateInput,
    user: dict[str, Any] = Depends(verify_jwt_token),
) -> TaskOut:
    """Create a periodic task owned by the authenticated user."""
    return tasks_service.create(body, user)


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(
    task_id: str,
    user: dict[str, Any] = Depends(verify_jwt_token),
) -> TaskOut:
    """Return one owned periodic task."""
    return tasks_service.get_task(task_id, user)


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: str,
    body: TaskUpdateInput,
    user: dict[str, Any] = Depends(verify_jwt_token),
) -> TaskOut:
    """Update fields on an owned periodic task."""
    return tasks_service.update(task_id, body, user)


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    user: dict[str, Any] = Depends(verify_jwt_token),
) -> dict[str, str]:
    """Delete an owned periodic task."""
    return tasks_service.delete(task_id, user)


@router.get("/{task_id}/runs", response_model=TaskRunsOut)
async def list_task_runs(
    task_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    user: dict[str, Any] = Depends(verify_jwt_token),
) -> TaskRunsOut:
    """List recent run metadata for an owned task."""
    return TaskRunsOut(runs=tasks_service.list_runs(task_id, user, limit=limit))


@router.post("/{task_id}/run", response_model=TaskRunOut)
async def run_task_now(
    task_id: str,
    user: dict[str, Any] = Depends(verify_jwt_token),
) -> TaskRunOut:
    """Execute the task immediately (dogfood / manual trigger)."""
    return await tasks_service.run_now(task_id, user)
