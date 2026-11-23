"""Thread id conventions for periodic task chats and run scratch threads."""

from __future__ import annotations

_TASK_CHAT_PREFIX = "task:"
_TASK_RUN_PREFIX = "task-run:"


def task_chat_thread_id(task_id: str) -> str:
    """
    Return the user-facing ephemeral chat thread for a task.

    Args:
        task_id: Durable task definition id.

    Returns:
        Thread id of the form ``task:{task_id}``.
    """
    return f"{_TASK_CHAT_PREFIX}{task_id}"


def task_run_thread_id(task_id: str) -> str:
    """
    Return the scratch thread used for a fresh scheduled agent invocation.

    Args:
        task_id: Durable task definition id.

    Returns:
        Thread id of the form ``task-run:{task_id}``.
    """
    return f"{_TASK_RUN_PREFIX}{task_id}"


def is_task_chat_thread(thread_id: str) -> bool:
    """
    Report whether ``thread_id`` is a periodic task chat thread.

    Args:
        thread_id: Candidate thread id.

    Returns:
        True when the id uses the ``task:`` prefix (not ``task-run:``).
    """
    if is_task_run_thread(thread_id):
        return False
    return thread_id.startswith(_TASK_CHAT_PREFIX)


def is_task_run_thread(thread_id: str) -> bool:
    """
    Report whether ``thread_id`` is a scheduled-run scratch thread.

    Args:
        thread_id: Candidate thread id.

    Returns:
        True when the id uses the ``task-run:`` prefix.
    """
    return thread_id.startswith(_TASK_RUN_PREFIX)


def parse_task_id_from_thread(thread_id: str) -> str | None:
    """
    Extract the task id from a task chat or run thread id.

    Args:
        thread_id: Thread id that may belong to a periodic task.

    Returns:
        Task id, or None when the thread is not task-related.
    """
    if thread_id.startswith(_TASK_RUN_PREFIX):
        return thread_id[len(_TASK_RUN_PREFIX) :] or None
    if thread_id.startswith(_TASK_CHAT_PREFIX):
        return thread_id[len(_TASK_CHAT_PREFIX) :] or None
    return None
