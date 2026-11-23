"""Schedule validation and next-run computation for periodic tasks."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Monday=0 … Sunday=6 (matches datetime.weekday()).
_DAY_NAMES = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tuesday": 1,
    "wed": 2,
    "wednesday": 2,
    "thu": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}


def validate_schedule(schedule: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize and validate a task schedule mapping.

    Expected shape::

        {"days_of_week": ["mon", "fri"] | [0, 4], "time": "08:00"}

    Args:
        schedule: Raw schedule from the client or storage.

    Returns:
        Normalized schedule with ``days_of_week`` as sorted unique ints 0–6
        and ``time`` as ``HH:MM``.

    Raises:
        ValueError: If the schedule is missing fields or invalid.
    """
    if not isinstance(schedule, dict):
        raise ValueError("Schedule must be an object.")
    days_raw = schedule.get("days_of_week")
    time_raw = schedule.get("time")
    if days_raw is None or time_raw is None:
        raise ValueError("Schedule requires days_of_week and time.")
    if not isinstance(days_raw, list) or not days_raw:
        raise ValueError("days_of_week must be a non-empty list.")
    days: set[int] = set()
    for item in days_raw:
        if isinstance(item, bool):
            raise ValueError(f"Invalid day_of_week: {item!r}")
        if isinstance(item, int):
            if item < 0 or item > 6:
                raise ValueError(f"day_of_week out of range: {item}")
            days.add(item)
            continue
        if isinstance(item, str):
            key = item.strip().lower()
            if key.isdigit():
                value = int(key)
                if value < 0 or value > 6:
                    raise ValueError(f"day_of_week out of range: {value}")
                days.add(value)
                continue
            if key not in _DAY_NAMES:
                raise ValueError(f"Unknown day_of_week: {item!r}")
            days.add(_DAY_NAMES[key])
            continue
        raise ValueError(f"Invalid day_of_week: {item!r}")
    if not isinstance(time_raw, str) or ":" not in time_raw:
        raise ValueError("time must be HH:MM.")
    parts = time_raw.strip().split(":")
    if len(parts) != 2:
        raise ValueError("time must be HH:MM.")
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError as exc:
        raise ValueError("time must be HH:MM.") from exc
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError("time must be a valid clock time.")
    return {
        "days_of_week": sorted(days),
        "time": f"{hour:02d}:{minute:02d}",
    }


def validate_timezone(tz_name: str) -> str:
    """
    Ensure ``tz_name`` is a valid IANA timezone.

    Args:
        tz_name: Timezone string (e.g. ``Europe/Madrid``).

    Returns:
        The same timezone name when valid.

    Raises:
        ValueError: If the timezone is unknown.
    """
    name = (tz_name or "").strip()
    if not name:
        raise ValueError("timezone cannot be empty.")
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {name!r}") from exc
    return name


def compute_next_run_at(
    schedule: dict[str, Any],
    tz_name: str,
    *,
    after: datetime | None = None,
) -> datetime:
    """
    Compute the next run instant (UTC) after ``after``.

    Args:
        schedule: Normalized schedule (``days_of_week``, ``time``).
        tz_name: IANA timezone for the wall-clock schedule.
        after: Instant to search from (defaults to now, UTC-aware).

    Returns:
        Timezone-aware datetime in UTC for the next matching wall time.
    """
    normalized = validate_schedule(schedule)
    tz = ZoneInfo(validate_timezone(tz_name))
    if after is None:
        after = datetime.now(timezone.utc)
    elif after.tzinfo is None:
        after = after.replace(tzinfo=timezone.utc)
    local_after = after.astimezone(tz)
    hour, minute = (int(part) for part in normalized["time"].split(":"))
    days = set(normalized["days_of_week"])
    # Search up to 8 days ahead so we always find the next weekday slot.
    for offset in range(0, 8):
        candidate_date = (local_after + timedelta(days=offset)).date()
        if candidate_date.weekday() not in days:
            continue
        candidate = datetime(
            candidate_date.year,
            candidate_date.month,
            candidate_date.day,
            hour,
            minute,
            tzinfo=tz,
        )
        if candidate > local_after:
            return candidate.astimezone(timezone.utc)
    raise RuntimeError("Could not compute next run time.")
