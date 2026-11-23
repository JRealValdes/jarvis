"""Pydantic schemas for periodic task HTTP APIs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TaskScheduleInput(BaseModel):
    """Wall-clock schedule in the task timezone."""

    days_of_week: list[int | str] = Field(
        ...,
        description="Weekdays (0=Mon…6=Sun or mon…sun).",
    )
    time: str = Field(..., description="Local time HH:MM.")


class TaskCreateInput(BaseModel):
    """Body for creating a periodic task."""

    title: str
    instruction: str
    schedule: TaskScheduleInput
    timezone: str = "Europe/Madrid"
    notify_policy: str = "always"
    enabled: bool = True


class TaskUpdateInput(BaseModel):
    """Body for partially updating a periodic task."""

    title: str | None = None
    instruction: str | None = None
    schedule: TaskScheduleInput | None = None
    timezone: str | None = None
    notify_policy: str | None = None
    enabled: bool | None = None


class TaskRunOut(BaseModel):
    """Run metadata for list/detail cards."""

    id: str
    task_id: str
    started_at: str
    finished_at: str | None
    status: str
    summary: str | None
    push_sent: bool
    error: str | None


class TaskOut(BaseModel):
    """Task definition plus list-friendly fields for the client."""

    id: str
    title: str
    instruction: str
    schedule: dict[str, Any]
    timezone: str
    notify_policy: str
    enabled: bool
    next_run_at: str | None
    next_reset_at: str | None
    next_reset_banner: str
    thread_id: str
    created_at: str
    updated_at: str
    latest_run: TaskRunOut | None = None


class TaskListOut(BaseModel):
    """List wrapper for task definitions."""

    tasks: list[TaskOut]


class TaskRunsOut(BaseModel):
    """List wrapper for task runs."""

    runs: list[TaskRunOut]
