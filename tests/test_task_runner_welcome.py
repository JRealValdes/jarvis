"""Periodic runs must not seed the interactive welcome as the task report."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from jarvis.agents.session.history import get_message_history
from jarvis.agents.session.orchestrator import JarvisSession
from jarvis.core.enums import ModelEnum
from jarvis.domain.chat.chat_state import ChatState
from jarvis.domain.tasks.thread_ids import task_chat_thread_id
from jarvis.domain.users.prompts import get_welcome_message
from jarvis.infrastructure.persistence.tasks.repository import (
    TaskDefinitionRecord,
)
import jarvis.infrastructure.persistence.tasks.repository as tasks_repo
from jarvis.infrastructure.tasks.runner import execute_task_run


def _user(real_name: str = "Ada") -> dict:
    return {
        "real_name": real_name,
        "jarvis_name": real_name,
        "is_female": False,
        "admin": False,
    }


def _task(task_id: str = "task-welcome-bug") -> TaskDefinitionRecord:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    return TaskDefinitionRecord(
        id=task_id,
        owner_real_name="Ada",
        title="Morning digest",
        instruction="Summarize overnight alerts.",
        schedule={"days_of_week": ["mon"], "time": "08:00"},
        timezone="UTC",
        enabled=True,
        notify_policy="never",
        created_at=now,
        updated_at=now,
        next_run_at=None,
    )


def test_fresh_authenticated_turn_returns_welcome_without_skip():
    """Documents the interactive short-circuit that broke scheduled runs."""
    user = _user()
    session = JarvisSession(
        ModelEnum.GPT_4O_MINI, "repro-welcome-short-circuit", user_info=user
    )

    async def _should_not_run(_messages: list, images=None) -> list[str]:
        raise AssertionError("model must not run on welcome short-circuit")

    session._run_model = _should_not_run  # type: ignore[method-assign]
    replies = asyncio.run(session.handle_turn("run the digest"))
    assert replies == [get_welcome_message(user)]
    assert session._chat_state == ChatState.JARVIS_WELCOME_MESSAGE


def test_skip_welcome_invokes_model_without_welcome_message():
    user = _user()
    session = JarvisSession(
        ModelEnum.GPT_4O_MINI, "machine-turn-skip-welcome", user_info=user
    )
    captured: dict = {}

    async def _fake(messages: list, images=None) -> list[str]:
        captured["messages"] = messages
        return ["Digest: all quiet overnight."]

    session._run_model = _fake  # type: ignore[method-assign]
    replies = asyncio.run(
        session.handle_turn("Summarize overnight alerts.", skip_welcome=True)
    )
    assert replies == ["Digest: all quiet overnight."]
    assert get_welcome_message(user) not in replies
    assert session._chat_state == ChatState.INITIALIZED

    messages = captured["messages"]
    assert isinstance(messages[0], SystemMessage)
    assert all(
        not (isinstance(msg, AIMessage) and msg.content == get_welcome_message(user))
        for msg in messages
    )
    assert isinstance(messages[-1], HumanMessage)
    assert "Summarize overnight alerts." in str(messages[-1].content)


def test_execute_task_run_passes_skip_welcome_and_seeds_report(
    tmp_path: Path, monkeypatch
):
    db = tmp_path / "tasks.db"
    monkeypatch.setattr(tasks_repo, "DB_PATH", str(db))
    monkeypatch.setattr(tasks_repo, "TASKS_DB_PATH", db)

    task = _task()
    ask = AsyncMock(return_value=["Digest: all quiet overnight."])
    with (
        patch(
            "jarvis.infrastructure.tasks.runner.get_user_by_field",
            return_value=_user(),
        ),
        patch("jarvis.agents.session.ask_jarvis", ask),
        patch("jarvis.agents.session.reset_session"),
    ):
        run = asyncio.run(
            execute_task_run(
                task,
                model=ModelEnum.GPT_4O_MINI,
                advance_schedule=False,
                send_push=False,
            )
        )

    assert ask.await_count == 1
    assert ask.await_args.kwargs.get("skip_welcome") is True
    assert run.status == "succeeded"
    assert run.summary == "Digest: all quiet overnight."

    history = get_message_history(
        task_chat_thread_id(task.id), ModelEnum.GPT_4O_MINI
    )
    assert history == [
        {"role": "assistant", "content": "Digest: all quiet overnight."}
    ]
    assert get_welcome_message(_user()) not in history[0]["content"]
