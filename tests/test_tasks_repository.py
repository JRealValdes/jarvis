"""Unit tests for periodic task SQLite repository."""

from pathlib import Path

import jarvis.infrastructure.persistence.tasks.repository as tasks_repo


def test_create_list_update_delete_task(tmp_path: Path, monkeypatch):
    db = tmp_path / "tasks.db"
    monkeypatch.setattr(tasks_repo, "DB_PATH", str(db))
    monkeypatch.setattr(tasks_repo, "TASKS_DB_PATH", db)

    task = tasks_repo.create_task(
        owner_real_name="Alice",
        title="Morning news",
        instruction="Search AI news and summarize.",
        schedule={"days_of_week": ["mon", "tue", "wed", "thu", "fri"], "time": "08:00"},
        timezone_name="Europe/Madrid",
        notify_policy="on_change",
    )
    assert task.id
    assert task.next_run_at
    assert task.schedule["days_of_week"] == [0, 1, 2, 3, 4]

    listed = tasks_repo.list_tasks_for_owner("Alice")
    assert len(listed) == 1
    assert listed[0].title == "Morning news"

    updated = tasks_repo.update_task(
        task.id, "Alice", title="AI digest", enabled=False
    )
    assert updated.title == "AI digest"
    assert updated.enabled is False
    assert updated.next_run_at is None

    run = tasks_repo.record_run(
        task_id=task.id, status="succeeded", summary="Nothing new."
    )
    assert run.status == "succeeded"
    latest = tasks_repo.latest_run_for_task(task.id)
    assert latest is not None
    assert latest.id == run.id

    assert tasks_repo.delete_task(task.id, "Alice") is True
    assert tasks_repo.get_task_for_owner(task.id, "Alice") is None
