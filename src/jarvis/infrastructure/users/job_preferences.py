"""Load per-user job / LinkedIn reply preferences from YAML under data/users."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from jarvis.core.paths import USERS_DATA_DIR

JOB_PREFERENCES_FILENAME = "job_preferences.yaml"


def job_preferences_path(real_name: str) -> Path:
    """
    Return the expected preferences file path for a user.

    Args:
        real_name: User identifier (folder under ``data/users/``).

    Returns:
        Path to ``job_preferences.yaml`` for that user.
    """
    normalized = real_name.strip().lower()
    return USERS_DATA_DIR / normalized / JOB_PREFERENCES_FILENAME


def load_job_preferences(real_name: str) -> dict[str, Any] | None:
    """
    Load job preferences YAML for ``real_name`` if the file exists.

    Args:
        real_name: User identifier.

    Returns:
        Parsed mapping, or ``None`` if the name is empty, the file is missing,
        or the file does not contain a YAML mapping.
    """
    if not real_name or not real_name.strip():
        return None
    path = job_preferences_path(real_name)
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        return None
    return data


def format_preferences_for_prompt(preferences: dict[str, Any] | None) -> str:
    """
    Render preferences as YAML text for an LLM prompt.

    Args:
        preferences: Loaded preferences mapping, or ``None``.

    Returns:
        Human-readable block stating that preferences are unset, or YAML text.
    """
    if not preferences:
        return (
            "No per-user job preferences file was found. "
            "Draft a generic professional reply and note that criteria are unset."
        )
    return yaml.safe_dump(preferences, sort_keys=False, allow_unicode=True).strip()
