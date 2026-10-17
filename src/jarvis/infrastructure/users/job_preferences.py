"""Load and save per-user job / LinkedIn reply preferences under data/users."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from jarvis.core.paths import USERS_DATA_DIR

JOB_PREFERENCES_FILENAME = "job_preferences.yaml"


def normalize_real_name(real_name: str) -> str:
    """
    Normalize a user id for filesystem paths.

    Args:
        real_name: Raw user identifier.

    Returns:
        Stripped lowercase name, or empty string if blank.
    """
    return real_name.strip().lower() if real_name else ""


def job_preferences_path(real_name: str) -> Path:
    """
    Return the expected preferences file path for a user.

    Args:
        real_name: User identifier (folder under ``data/users/``).

    Returns:
        Path to ``job_preferences.yaml`` for that user.
    """
    return USERS_DATA_DIR / normalize_real_name(real_name) / JOB_PREFERENCES_FILENAME


def load_job_preferences(real_name: str) -> dict[str, Any] | None:
    """
    Load job preferences YAML for ``real_name`` if the file exists.

    Args:
        real_name: User identifier.

    Returns:
        Parsed mapping, or ``None`` if the name is empty, the file is missing,
        or the file does not contain a YAML mapping.
    """
    if not normalize_real_name(real_name):
        return None
    path = job_preferences_path(real_name)
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        return None
    return data


def deep_merge_preferences(
    base: dict[str, Any],
    patch: dict[str, Any],
) -> dict[str, Any]:
    """
    Merge ``patch`` into ``base`` recursively for nested mappings.

    Non-mapping values (including lists) in ``patch`` replace the base value.

    Args:
        base: Existing preferences.
        patch: Partial update.

    Returns:
        New merged mapping (inputs are not mutated).
    """
    result: dict[str, Any] = dict(base)
    for key, value in patch.items():
        current = result.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            result[key] = deep_merge_preferences(current, value)
        else:
            result[key] = value
    return result


def parse_preferences_yaml(text: str) -> dict[str, Any]:
    """
    Parse a YAML preferences document into a mapping.

    Args:
        text: YAML document text.

    Returns:
        Preferences mapping.

    Raises:
        ValueError: If the text is empty or not a YAML mapping.
    """
    if not text or not text.strip():
        raise ValueError("Preferences YAML is empty.")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("Preferences YAML must be a mapping at the top level.")
    return data


def save_job_preferences(
    real_name: str,
    preferences: dict[str, Any],
    *,
    merge: bool = True,
) -> Path:
    """
    Write job preferences for ``real_name`` to disk.

    Args:
        real_name: User identifier.
        preferences: Mapping to store (or merge when ``merge`` is True).
        merge: If True and a file exists, deep-merge into it; otherwise replace.

    Returns:
        Path written.

    Raises:
        ValueError: If ``real_name`` is blank or ``preferences`` is not a mapping.
    """
    normalized = normalize_real_name(real_name)
    if not normalized:
        raise ValueError("real_name is required to save job preferences.")
    if not isinstance(preferences, dict):
        raise ValueError("preferences must be a mapping.")

    path = job_preferences_path(normalized)
    to_write = preferences
    if merge:
        existing = load_job_preferences(normalized)
        if existing is not None:
            to_write = deep_merge_preferences(existing, preferences)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(to_write, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


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


_AVOID_KEY_NAMES = frozenset(
    {
        "avoid",
        "avoid_phrases",
        "avoid_phrase",
        "do_not_use",
        "phrases_to_avoid",
    }
)


def _constraint_texts(value: Any) -> list[str]:
    """Normalize a preferences value into constraint strings."""
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        texts: list[str] = []
        for item in value:
            texts.extend(_constraint_texts(item))
        return texts
    return []


def extract_avoid_constraints(preferences: dict[str, Any] | None) -> list[str]:
    """
    Collect phrasing constraints the draft must not violate.

    Looks for known keys such as ``avoid``, ``avoid_phrases`` under
    ``reply_style``, ``tone_and_language``, and nested mappings.

    Args:
        preferences: Loaded preferences mapping, or ``None``.

    Returns:
        Deduplicated list of constraint strings (order preserved).
    """
    if not preferences:
        return []

    found: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(key, str) and key.lower() in _AVOID_KEY_NAMES:
                    found.extend(_constraint_texts(value))
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(preferences)
    deduped: list[str] = []
    seen: set[str] = set()
    for text in found:
        if text not in seen:
            seen.add(text)
            deduped.append(text)
    return deduped


def format_avoid_constraints_for_prompt(constraints: list[str]) -> str:
    """
    Render avoid constraints as a prominent prompt block.

    Args:
        constraints: Strings from ``extract_avoid_constraints``.

    Returns:
        Human-readable hard-constraint section, or a short note if empty.
    """
    if not constraints:
        return "None specified beyond general professionalism."
    lines = [
        "These are HARD constraints. Do not use these phrases, patterns, or "
        "close paraphrases in ANY language (including Spanish translations):",
    ]
    for item in constraints:
        lines.append(f"- {item}")
    return "\n".join(lines)
