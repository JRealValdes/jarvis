"""In-process periodic task scheduler (FastAPI lifespan)."""

from __future__ import annotations

import asyncio
import logging

from jarvis.infrastructure.persistence.tasks.repository import (
    get_task,
    init_tasks_db,
    list_tasks_due,
)
from jarvis.infrastructure.tasks.runner import execute_task_run

logger = logging.getLogger(__name__)

_POLL_SECONDS = 30.0
_scheduler_task: asyncio.Task[None] | None = None
_stop_event: asyncio.Event | None = None


async def _tick_once() -> None:
    """Load due tasks and execute each one sequentially."""
    due = list_tasks_due()
    for task in due:
        # Re-read in case a concurrent update disabled the task.
        current = get_task(task.id)
        if current is None or not current.enabled:
            continue
        try:
            await execute_task_run(current)
        except Exception:
            logger.exception("Scheduler failed while running task %s", task.id)


async def _scheduler_loop(stop_event: asyncio.Event) -> None:
    """Poll for due tasks until ``stop_event`` is set."""
    init_tasks_db()
    logger.info("Periodic task scheduler started (poll=%.0fs)", _POLL_SECONDS)
    while not stop_event.is_set():
        try:
            await _tick_once()
        except Exception:
            logger.exception("Periodic task scheduler tick failed")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=_POLL_SECONDS)
        except asyncio.TimeoutError:
            continue
    logger.info("Periodic task scheduler stopped")


def start_task_scheduler() -> None:
    """
    Start the background scheduler on the running event loop.

    Returns:
        None. Idempotent when already running.
    """
    global _scheduler_task, _stop_event
    if _scheduler_task is not None and not _scheduler_task.done():
        return
    _stop_event = asyncio.Event()
    _scheduler_task = asyncio.create_task(
        _scheduler_loop(_stop_event), name="jarvis-task-scheduler"
    )


async def stop_task_scheduler() -> None:
    """
    Signal the scheduler to stop and await its exit.

    Returns:
        None.
    """
    global _scheduler_task, _stop_event
    if _stop_event is not None:
        _stop_event.set()
    if _scheduler_task is not None:
        try:
            await asyncio.wait_for(_scheduler_task, timeout=5.0)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            _scheduler_task.cancel()
        _scheduler_task = None
    _stop_event = None
