"""User identification from natural language."""

import re

from infrastructure.persistence.users.repository import get_user_by_field

_IDENTIFICATION_PATTERN = re.compile(r"\bsoy\s+([^\s,.!?]+)", re.IGNORECASE)


def find_user_by_prompt(prompt: str) -> dict | None:
    """
    Detect ``soy <name>`` in the prompt and look up the user by access_name.

    Args:
        prompt: Free-form user text.

    Returns:
        User dict if found; None if there is no pattern or no match.
    """
    match = _IDENTIFICATION_PATTERN.search(prompt)
    if not match:
        return None

    access_candidate = match.group(1).strip()
    return get_user_by_field("access_name", access_candidate, is_sensitive=True)
