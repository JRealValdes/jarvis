"""Unit tests for periodic task schedule helpers."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from jarvis.domain.tasks.schedule import (
    compute_next_run_at,
    validate_schedule,
    validate_timezone,
)
from jarvis.domain.tasks.thread_ids import (
    is_task_chat_thread,
    is_task_run_thread,
    parse_task_id_from_thread,
    task_chat_thread_id,
    task_run_thread_id,
)


def test_validate_schedule_normalizes_day_names():
    result = validate_schedule(
        {"days_of_week": ["Mon", "fri", 2], "time": "8:05"}
    )
    assert result == {"days_of_week": [0, 2, 4], "time": "08:05"}


def test_validate_schedule_rejects_empty_days():
    with pytest.raises(ValueError, match="non-empty"):
        validate_schedule({"days_of_week": [], "time": "08:00"})


def test_validate_timezone_rejects_unknown():
    with pytest.raises(ValueError, match="Unknown timezone"):
        validate_timezone("Not/AZone")


def test_compute_next_run_at_skips_past_slot_same_day():
    # Wednesday 2024-06-05 09:00 Europe/Madrid → next Fri 08:00
    after = datetime(2024, 6, 5, 9, 0, tzinfo=ZoneInfo("Europe/Madrid"))
    next_at = compute_next_run_at(
        {"days_of_week": ["wed", "fri"], "time": "08:00"},
        "Europe/Madrid",
        after=after,
    )
    local = next_at.astimezone(ZoneInfo("Europe/Madrid"))
    assert local.weekday() == 4
    assert local.hour == 8
    assert local.minute == 0


def test_thread_id_helpers():
    assert task_chat_thread_id("abc") == "task:abc"
    assert task_run_thread_id("abc") == "task-run:abc"
    assert is_task_chat_thread("task:abc")
    assert not is_task_chat_thread("task-run:abc")
    assert is_task_run_thread("task-run:abc")
    assert parse_task_id_from_thread("task:abc") == "abc"
    assert parse_task_id_from_thread("task-run:abc") == "abc"
    assert parse_task_id_from_thread("Alice") is None
