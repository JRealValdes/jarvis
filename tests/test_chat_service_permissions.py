"""ChatService authorization (action-specific ForbiddenError)."""

from pathlib import Path

import pytest

from jarvis.api.errors import ForbiddenError
from jarvis.api.services.chat_service import ChatService
import jarvis.infrastructure.persistence.tasks.repository as tasks_repo


def test_non_admin_cannot_reset_other_thread():
    user = {"real_name": "Alice", "admin": False}
    with pytest.raises(ForbiddenError) as exc:
        ChatService()._resolve_thread_id("Bob", user, action="reset")
    assert "reset other users" in str(exc.value).lower()


def test_non_admin_cannot_read_other_thread_history():
    user = {"real_name": "Alice", "admin": False}
    with pytest.raises(ForbiddenError) as exc:
        ChatService()._resolve_thread_id("Bob", user, action="read")
    assert "history" in str(exc.value).lower()


def test_owner_can_ask_and_read_own_task_thread(tmp_path: Path, monkeypatch):
    db = tmp_path / "tasks.db"
    monkeypatch.setattr(tasks_repo, "DB_PATH", str(db))
    monkeypatch.setattr(tasks_repo, "TASKS_DB_PATH", db)
    task = tasks_repo.create_task(
        owner_real_name="Alice",
        title="Digest",
        instruction="Summarize news.",
        schedule={"days_of_week": ["mon"], "time": "08:00"},
        timezone_name="UTC",
    )
    user = {"real_name": "Alice", "admin": False}
    thread = f"task:{task.id}"
    assert ChatService()._resolve_thread_id(thread, user, action="ask") == thread
    assert ChatService()._resolve_thread_id(thread, user, action="read") == thread
    with pytest.raises(ForbiddenError, match="scheduled run"):
        ChatService()._resolve_thread_id(thread, user, action="reset")


def test_owner_cannot_use_task_run_scratch_thread():
    user = {"real_name": "Alice", "admin": False}
    with pytest.raises(ForbiddenError):
        ChatService()._resolve_thread_id("task-run:abc", user, action="ask")
