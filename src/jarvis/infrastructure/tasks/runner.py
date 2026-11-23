"""Execute one periodic task run and seed the ephemeral task chat.

Session/agent imports stay inside ``execute_task_run`` so this module can be
imported by tool definitions without creating an import cycle:

``tools.builtins`` → runner → ``agents.session`` → factory → ``tools.builtins``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from jarvis.core.config import DEFAULT_MODEL
from jarvis.core.enums import ModelEnum
from jarvis.domain.tasks.schedule import compute_next_run_at
from jarvis.domain.tasks.thread_ids import task_chat_thread_id, task_run_thread_id
from jarvis.infrastructure.persistence.tasks.repository import (
    TaskDefinitionRecord,
    TaskRunRecord,
    record_run,
    set_next_run_at,
    update_run,
)
from jarvis.infrastructure.persistence.users.repository import get_user_by_field

logger = logging.getLogger(__name__)

_SUMMARY_MAX_CHARS = 280


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _summarize(report: str) -> str:
    """Build a short list-card summary from the full run report."""
    text = " ".join((report or "").split())
    if len(text) <= _SUMMARY_MAX_CHARS:
        return text
    return text[: _SUMMARY_MAX_CHARS - 1].rstrip() + "…"


def _user_info_for_owner(owner_real_name: str) -> dict:
    """
    Load JWT-shaped user claims for a scheduled run.

    Args:
        owner_real_name: Task owner.

    Returns:
        User dict suitable for ``ask_jarvis``.

    Raises:
        LookupError: If the owner is missing from the users database.
    """
    user = get_user_by_field("real_name", owner_real_name, is_sensitive=False)
    if not user:
        raise LookupError(f"Task owner not found: {owner_real_name}")
    return {
        "sub": owner_real_name,
        "real_name": user["real_name"],
        "jarvis_name": user.get("jarvis_name") or owner_real_name,
        "is_female": bool(user.get("is_female")),
        "admin": bool(user.get("admin")),
    }


async def _notify_task_push(
    *,
    owner_real_name: str,
    task_id: str,
    title: str,
    summary: str,
) -> bool:
    """
    Send a task-complete push when the push substrate is installed.

    Import is deferred so the core tasks slice can load without devices/push.
    """
    try:
        from jarvis.infrastructure.push.sender import maybe_send_task_push
    except ImportError:
        logger.debug("Push sender unavailable; skip task notify")
        return False
    return await maybe_send_task_push(
        owner_real_name=owner_real_name,
        task_id=task_id,
        title=title,
        summary=summary,
    )


def _should_notify(
    policy: str, *, summary: str, previous_summary: str | None
) -> bool:
    """
    Decide whether a push should be sent for this run.

    Args:
        policy: ``always``, ``never``, or ``on_change``.
        summary: Current run summary.
        previous_summary: Prior succeeded-run summary, if any.

    Returns:
        True when a notification should be attempted.
    """
    if policy == "never":
        return False
    if policy == "always":
        return True
    if policy == "on_change":
        return (summary or "").strip() != (previous_summary or "").strip()
    return False


def _build_run_prompt(task: TaskDefinitionRecord, previous: TaskRunRecord | None) -> str:
    """
    Build the fresh agent prompt for a scheduled run.

    Args:
        task: Task definition.
        previous: Latest prior run (for optional dedup context).

    Returns:
        Prompt string for ``ask_jarvis``.
    """
    parts = [
        "You are running a scheduled periodic task for the user.",
        "Complete the goal below using tools as needed.",
        "Reply with a clear report the user can read as the first message "
        "in a dedicated task chat. Do not ask clarifying questions unless "
        "the goal is impossible without them.",
        "",
        f"Task title: {task.title}",
        f"Goal:\n{task.instruction}",
    ]
    if previous and previous.summary and previous.status == "succeeded":
        parts.extend(
            [
                "",
                "Previous run summary (for deduplication / change detection only; "
                "do not repeat unchanged fluff):",
                previous.summary,
            ]
        )
    return "\n".join(parts)


async def execute_task_run(
    task: TaskDefinitionRecord,
    *,
    model: ModelEnum = DEFAULT_MODEL,
    advance_schedule: bool = True,
    send_push: bool = True,
) -> TaskRunRecord:
    """
    Run one task: fresh agent invocation, store metadata, seed task chat.

    Args:
        task: Definition to execute.
        model: LLM model for the run.
        advance_schedule: When True, recompute ``next_run_at`` after the run.
        send_push: When True, attempt push if the notify policy matches.

    Returns:
        Final run metadata row.
    """
    # Deferred: keeps tool-module imports free of the agent package cycle.
    from jarvis.agents.session import ask_jarvis, reset_session
    from jarvis.agents.session.seed import seed_assistant_message
    from jarvis.infrastructure.persistence.tasks.repository import list_runs_for_task

    prior: TaskRunRecord | None = None
    for candidate in list_runs_for_task(task.id, limit=5):
        if candidate.status in {"succeeded", "failed"}:
            prior = candidate
            break

    started = _utc_now_iso()
    run = record_run(task_id=task.id, status="running", started_at=started)

    run_thread = task_run_thread_id(task.id)
    chat_thread = task_chat_thread_id(task.id)
    reset_session(run_thread, model=model)

    try:
        user_info = _user_info_for_owner(task.owner_real_name)
        prompt = _build_run_prompt(task, prior)
        fragments = await ask_jarvis(
            prompt,
            model,
            run_thread,
            user_info=user_info,
        )
        report = "\n\n".join(
            part for part in fragments if isinstance(part, str) and part.strip()
        ).strip()
        summary = _summarize(report)
        seed_assistant_message(
            chat_thread,
            report,
            real_name=task.owner_real_name,
            model=model,
            reset_first=True,
        )
        push_sent = False
        if send_push and _should_notify(
            task.notify_policy,
            summary=summary,
            previous_summary=prior.summary if prior else None,
        ):
            push_sent = await _notify_task_push(
                owner_real_name=task.owner_real_name,
                task_id=task.id,
                title=task.title,
                summary=summary,
            )
        updated = update_run(
            run.id,
            status="succeeded",
            summary=summary,
            push_sent=push_sent,
            finished_at=_utc_now_iso(),
        )
        assert updated is not None
        run = updated
    except Exception as exc:
        logger.exception("Periodic task run failed for %s", task.id)
        error_text = str(exc) or exc.__class__.__name__
        seed_assistant_message(
            chat_thread,
            f"This scheduled run failed:\n\n{error_text}",
            real_name=task.owner_real_name,
            model=model,
            reset_first=True,
        )
        updated = update_run(
            run.id,
            status="failed",
            summary=_summarize(f"Run failed: {error_text}"),
            error=error_text,
            finished_at=_utc_now_iso(),
        )
        assert updated is not None
        run = updated
    finally:
        reset_session(run_thread, model=model)
        if advance_schedule and task.enabled:
            next_at = (
                compute_next_run_at(task.schedule, task.timezone)
                .replace(microsecond=0)
                .isoformat()
            )
            set_next_run_at(task.id, next_at)
        elif advance_schedule and not task.enabled:
            set_next_run_at(task.id, None)

    return run
