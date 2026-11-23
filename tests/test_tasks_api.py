"""HTTP smoke tests for periodic task routes (no live LLM)."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import jwt
from fastapi.testclient import TestClient

from jarvis.api.app import app
from jarvis.core.config import JWT_ALGORITHM
import jarvis.infrastructure.persistence.tasks.repository as tasks_repo


def _user_token(real_name: str = "Alice", admin: bool = False) -> str:
    payload = {
        "sub": real_name,
        "real_name": real_name,
        "jarvis_name": "Sir",
        "is_female": False,
        "admin": admin,
        "exp": 9999999999,
    }
    secret = __import__("os").environ["JWT_SECRET_KEY"]
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def test_tasks_crud_and_list(tmp_path: Path, monkeypatch):
    db = tmp_path / "tasks.db"
    monkeypatch.setattr(tasks_repo, "DB_PATH", str(db))
    monkeypatch.setattr(tasks_repo, "TASKS_DB_PATH", db)

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {_user_token()}"}
    create = client.post(
        "/tasks",
        headers=headers,
        json={
            "title": "News",
            "instruction": "Check AI news.",
            "schedule": {"days_of_week": ["mon"], "time": "08:00"},
            "timezone": "UTC",
            "notify_policy": "always",
        },
    )
    assert create.status_code == 200, create.text
    body = create.json()
    assert body["title"] == "News"
    assert body["thread_id"].startswith("task:")
    assert body["next_reset_banner"]
    task_id = body["id"]

    listed = client.get("/tasks", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()["tasks"]) == 1

    got = client.get(f"/tasks/{task_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["id"] == task_id

    patched = client.patch(
        f"/tasks/{task_id}",
        headers=headers,
        json={"title": "AI News"},
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "AI News"

    fake_run = AsyncMock(
        return_value=tasks_repo.TaskRunRecord(
            id="run-1",
            task_id=task_id,
            started_at="2024-01-01T00:00:00+00:00",
            finished_at="2024-01-01T00:00:01+00:00",
            status="succeeded",
            summary="Quiet day.",
            push_sent=False,
            error=None,
        )
    )
    with patch(
        "jarvis.api.services.tasks_service.execute_task_run", fake_run
    ):
        ran = client.post(f"/tasks/{task_id}/run", headers=headers)
    assert ran.status_code == 200
    assert ran.json()["summary"] == "Quiet day."

    deleted = client.delete(f"/tasks/{task_id}", headers=headers)
    assert deleted.status_code == 200
    assert client.get(f"/tasks/{task_id}", headers=headers).status_code == 404
