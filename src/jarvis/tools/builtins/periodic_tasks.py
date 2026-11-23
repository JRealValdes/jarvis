"""LangChain tools to create, list, update, and run periodic tasks."""

from __future__ import annotations

import json
from typing import Annotated, Any

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from jarvis.infrastructure.persistence.tasks.repository import (
    create_task,
    delete_task,
    get_task_for_owner,
    list_tasks_for_owner,
    update_task,
)
from jarvis.infrastructure.tasks.runner import execute_task_run


def _require_real_name(real_name: str) -> str | None:
    """Return a normalized real_name or an error string."""
    normalized = (real_name or "").strip()
    if not normalized:
        return None
    return normalized


@tool
def list_periodic_tasks_tool(
    real_name: Annotated[str, InjectedState("real_name")] = "",
) -> str:
    """
    List the user's configured periodic tasks (schedule, notify policy, next run).

    Call when the user asks what scheduled jobs they have, or before editing one.
    """
    owner = _require_real_name(real_name)
    if owner is None:
        return (
            "Cannot list periodic tasks: no real_name in the session. "
            "Identify or authenticate the user first."
        )
    tasks = list_tasks_for_owner(owner)
    if not tasks:
        return "No periodic tasks configured yet."
    lines: list[str] = []
    for task in tasks:
        lines.append(
            f"- id={task.id} | {task.title} | enabled={task.enabled} | "
            f"tz={task.timezone} | schedule={json.dumps(task.schedule)} | "
            f"notify={task.notify_policy} | next_run_at={task.next_run_at}"
        )
    return "Periodic tasks:\n" + "\n".join(lines)


@tool
def create_periodic_task_tool(
    title: str,
    instruction: str,
    days_of_week: list[str | int],
    time: str,
    timezone: str = "Europe/Madrid",
    notify_policy: str = "always",
    enabled: bool = True,
    confirmed: bool = False,
    real_name: Annotated[str, InjectedState("real_name")] = "",
) -> str:
    """
    Create a periodic task for the session user.

    Interview the user for title, goal/instruction, weekdays, local time,
    timezone, and notify policy (always | never | on_change). Summarize the
    plan, then call with confirmed=true only after explicit approval.

    Parameters:
    - title: Short label
    - instruction: Goal for each run (English preferred)
    - days_of_week: e.g. ["mon","tue","wed","thu","fri"] or [0,1,2,3,4]
    - time: Local HH:MM
    - timezone: IANA timezone (default Europe/Madrid)
    - notify_policy: always | never | on_change
    - enabled: whether the scheduler should fire it
    - confirmed: must be true to write
    """
    owner = _require_real_name(real_name)
    if owner is None:
        return (
            "Cannot create periodic task: no real_name in the session. "
            "Identify or authenticate the user first."
        )
    if not confirmed:
        return (
            "Refusing to create the task until confirmed=true after the user "
            "approves the summary."
        )
    try:
        task = create_task(
            owner_real_name=owner,
            title=title,
            instruction=instruction,
            schedule={"days_of_week": days_of_week, "time": time},
            timezone_name=timezone,
            notify_policy=notify_policy,
            enabled=enabled,
        )
    except ValueError as exc:
        return f"Could not create periodic task: {exc}"
    return (
        f"Created periodic task id={task.id} title={task.title!r} "
        f"next_run_at={task.next_run_at}."
    )


@tool
def update_periodic_task_tool(
    task_id: str,
    title: str | None = None,
    instruction: str | None = None,
    days_of_week: list[str | int] | None = None,
    time: str | None = None,
    timezone: str | None = None,
    notify_policy: str | None = None,
    enabled: bool | None = None,
    confirmed: bool = False,
    real_name: Annotated[str, InjectedState("real_name")] = "",
) -> str:
    """
    Update an existing periodic task owned by the session user.

    Pass only fields that should change. Summarize the change, then call with
    confirmed=true after the user approves.
    """
    owner = _require_real_name(real_name)
    if owner is None:
        return (
            "Cannot update periodic task: no real_name in the session. "
            "Identify or authenticate the user first."
        )
    if not confirmed:
        return (
            "Refusing to update the task until confirmed=true after the user "
            "approves the summary."
        )
    schedule: dict[str, Any] | None = None
    if days_of_week is not None or time is not None:
        existing = get_task_for_owner(task_id, owner)
        if existing is None:
            return f"Task not found: {task_id}"
        schedule = {
            "days_of_week": (
                days_of_week
                if days_of_week is not None
                else existing.schedule["days_of_week"]
            ),
            "time": time if time is not None else existing.schedule["time"],
        }
    try:
        task = update_task(
            task_id,
            owner,
            title=title,
            instruction=instruction,
            schedule=schedule,
            timezone_name=timezone,
            notify_policy=notify_policy,
            enabled=enabled,
        )
    except LookupError:
        return f"Task not found: {task_id}"
    except ValueError as exc:
        return f"Could not update periodic task: {exc}"
    return (
        f"Updated periodic task id={task.id} title={task.title!r} "
        f"next_run_at={task.next_run_at}."
    )


@tool
def delete_periodic_task_tool(
    task_id: str,
    confirmed: bool = False,
    real_name: Annotated[str, InjectedState("real_name")] = "",
) -> str:
    """
    Delete a periodic task owned by the session user.

    Confirm with the user first, then call with confirmed=true.
    """
    owner = _require_real_name(real_name)
    if owner is None:
        return (
            "Cannot delete periodic task: no real_name in the session. "
            "Identify or authenticate the user first."
        )
    if not confirmed:
        return (
            "Refusing to delete the task until confirmed=true after the user "
            "approves."
        )
    if not delete_task(task_id, owner):
        return f"Task not found: {task_id}"
    return f"Deleted periodic task id={task_id}."


@tool
async def run_periodic_task_now_tool(
    task_id: str,
    confirmed: bool = False,
    real_name: Annotated[str, InjectedState("real_name")] = "",
) -> str:
    """
    Run a periodic task immediately (does not wait for the schedule).

    Confirm with the user first, then call with confirmed=true.
    """
    owner = _require_real_name(real_name)
    if owner is None:
        return (
            "Cannot run periodic task: no real_name in the session. "
            "Identify or authenticate the user first."
        )
    if not confirmed:
        return (
            "Refusing to run the task until confirmed=true after the user "
            "approves."
        )
    task = get_task_for_owner(task_id, owner)
    if task is None:
        return f"Task not found: {task_id}"
    run = await execute_task_run(task, advance_schedule=True, send_push=True)
    return (
        f"Run finished for task {task_id}: status={run.status} "
        f"summary={run.summary!r}."
    )
