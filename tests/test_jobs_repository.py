"""Unit tests for async chat job persistence."""

from pathlib import Path

import jarvis.infrastructure.persistence.jobs.repository as jobs_repo


def test_create_and_complete_job(tmp_path: Path, monkeypatch):
    db = tmp_path / "jobs.db"
    monkeypatch.setattr(jobs_repo, "DB_PATH", str(db))
    monkeypatch.setattr(jobs_repo, "JOBS_DB_PATH", db)

    job = jobs_repo.create_job(owner_real_name="Alice", thread_id="Alice")
    assert job.status == "running"
    done = jobs_repo.update_job(
        job.id, status="done", response=["Hello"]
    )
    assert done is not None
    assert done.status == "done"
    assert done.finished_at
    owned = jobs_repo.get_job_for_owner(job.id, "Alice")
    assert owned is not None
    assert jobs_repo.get_job_for_owner(job.id, "Bob") is None
