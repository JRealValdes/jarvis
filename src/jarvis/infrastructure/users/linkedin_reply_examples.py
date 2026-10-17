"""Load per-user sample LinkedIn replies used as style references when drafting."""

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
    if not normalize_real_name(real_name):
        return []
    path = linkedin_reply_examples_path(real_name)
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    raw_items: list[Any]
    if isinstance(data, list):
        raw_items = data
    elif isinstance(data, dict):
        examples = data.get("examples")
        if not isinstance(examples, list):
            return []
        raw_items = examples
    else:
        return []

    bodies: list[str] = []
    for item in raw_items:
        body = _example_body(item)
        if body is not None:
            bodies.append(body)
    return bodies


def format_reply_examples_for_prompt(examples: list[str]) -> str:
    """
    Render sample replies for an LLM prompt.

    Args:
        examples: Complete sample message bodies.

    Returns:
        Human-readable block, or a short note when there are no examples.
    """
    if not examples:
        return (
            "No sample replies on file. Draft from job preferences and "
            "reply_style only."
        )
    parts: list[str] = []
    for index, body in enumerate(examples, start=1):
        parts.append(f"### Example {index}\n{body}")
    return "\n\n".join(parts)
