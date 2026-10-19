"""Load and save per-user sample LinkedIn replies used as style references."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from jarvis.core.paths import USERS_DATA_DIR
from jarvis.infrastructure.users.job_preferences import normalize_real_name

LINKEDIN_REPLY_EXAMPLES_FILENAME = "linkedin_reply_examples.yaml"


def linkedin_reply_examples_path(real_name: str) -> Path:
    """
    Return the expected sample-replies file path for a user.

    Args:
        real_name: User identifier (folder under ``data/users/``).

    Returns:
        Path to ``linkedin_reply_examples.yaml`` for that user.
    """
    return (
        USERS_DATA_DIR
        / normalize_real_name(real_name)
        / LINKEDIN_REPLY_EXAMPLES_FILENAME
    )


def _example_body(item: Any) -> str | None:
    """Extract a non-empty message body from a YAML example entry."""
    if isinstance(item, str):
        text = item.strip()
        return text or None
    if isinstance(item, dict):
        for key in ("body", "text", "message"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def _example_label(item: Any) -> str:
    """Extract an optional label from a mapping entry."""
    if isinstance(item, dict):
        label = item.get("label")
        if isinstance(label, str) and label.strip():
            return label.strip()
    return ""


def _raw_example_items(real_name: str) -> list[Any]:
    """Return raw YAML example items for ``real_name``, or an empty list."""
    if not normalize_real_name(real_name):
        return []
    path = linkedin_reply_examples_path(real_name)
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        examples = data.get("examples")
        if isinstance(examples, list):
            return examples
    return []


def load_linkedin_reply_example_entries(real_name: str) -> list[dict[str, str]]:
    """
    Load sample replies as ``{label, body}`` entries.

    Args:
        real_name: User identifier.

    Returns:
        List of entries with non-empty ``body``; ``label`` may be empty.
    """
    entries: list[dict[str, str]] = []
    for item in _raw_example_items(real_name):
        body = _example_body(item)
        if body is None:
            continue
        entries.append({"label": _example_label(item), "body": body})
    return entries


def load_linkedin_reply_examples(real_name: str) -> list[str]:
    """
    Load complete sample reply texts for ``real_name`` if the file exists.

    Accepted shapes:
    - a YAML list of strings (or ``{body|text|message: ...}`` mappings)
    - a mapping with an ``examples`` list in that same form

    Args:
        real_name: User identifier.

    Returns:
        List of non-empty sample message bodies, or an empty list if unset/invalid.
    """
    return [entry["body"] for entry in load_linkedin_reply_example_entries(real_name)]


def save_linkedin_reply_examples(
    real_name: str,
    entries: list[dict[str, str]],
) -> Path:
    """
    Replace the sample-replies file with ``entries``.

    Args:
        real_name: User identifier.
        entries: List of ``{label, body}`` mappings (``label`` optional).

    Returns:
        Path written.

    Raises:
        ValueError: If ``real_name`` is blank or no valid bodies remain.
    """
    normalized = normalize_real_name(real_name)
    if not normalized:
        raise ValueError("real_name is required to save LinkedIn reply examples.")

    serialized: list[dict[str, str]] = []
    for entry in entries:
        body = (entry.get("body") or "").strip()
        if not body:
            continue
        item: dict[str, str] = {"body": body}
        label = (entry.get("label") or "").strip()
        if label:
            item = {"label": label, "body": body}
        serialized.append(item)

    if not serialized:
        raise ValueError("At least one non-empty example body is required.")

    path = linkedin_reply_examples_path(normalized)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {"examples": serialized},
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return path


def append_linkedin_reply_example(
    real_name: str,
    body: str,
    *,
    label: str = "",
) -> Path:
    """
    Append one sample reply to the user's examples file.

    Args:
        real_name: User identifier.
        body: Complete sample message text.
        label: Optional short label for the example.

    Returns:
        Path written.

    Raises:
        ValueError: If ``real_name`` or ``body`` is blank.
    """
    text = body.strip() if body else ""
    if not text:
        raise ValueError("Example body is empty.")
    entries = load_linkedin_reply_example_entries(real_name)
    entries.append({"label": label.strip(), "body": text})
    return save_linkedin_reply_examples(real_name, entries)


def format_reply_examples_for_prompt(
    examples: list[str] | list[dict[str, str]],
) -> str:
    """
    Render sample replies for an LLM prompt.

    Args:
        examples: Complete sample message bodies, or ``{label, body}`` entries.
            Labels are optional scenario hints (e.g. work-mode clarification).

    Returns:
        Human-readable block, or a short note when there are no examples.
    """
    if not examples:
        return (
            "No sample replies on file. Draft from job preferences and "
            "reply_style only."
        )
    parts: list[str] = []
    for index, item in enumerate(examples, start=1):
        if isinstance(item, dict):
            body = (item.get("body") or "").strip()
            label = (item.get("label") or "").strip()
        else:
            body = str(item).strip()
            label = ""
        if not body:
            continue
        heading = f"### Example {index}"
        if label:
            heading = f"{heading} ({label})"
        parts.append(f"{heading}\n{body}")
    if not parts:
        return (
            "No sample replies on file. Draft from job preferences and "
            "reply_style only."
        )
    return "\n\n".join(parts)

