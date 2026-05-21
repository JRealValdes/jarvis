"""Identificación de usuarios a partir del lenguaje natural."""

import re

from infrastructure.persistence.users.repository import get_user_by_field

_IDENTIFICATION_PATTERN = re.compile(r"\bsoy\s+([^\s,.!?]+)", re.IGNORECASE)


def find_user_by_prompt(prompt: str) -> dict | None:
    """
    Detecta ``soy <nombre>`` en el prompt y busca usuario por access_name.

    Args:
        prompt: Texto libre del usuario.

    Returns:
        Dict de usuario si existe; None si no hay patrón o no hay match.
    """
    match = _IDENTIFICATION_PATTERN.search(prompt)
    if not match:
        return None

    access_candidate = match.group(1).strip()
    return get_user_by_field("access_name", access_candidate, is_sensitive=True)
