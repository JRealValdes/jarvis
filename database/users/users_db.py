"""
User access — compatibility layer.

New code should use:
- ``infrastructure.persistence.users.repository`` for SQL
- ``domain.users.identification`` for prompt-based identification
"""

from domain.users.identification import find_user_by_prompt
from infrastructure.persistence.users.repository import (
    DB_PATH,
    delete_user_by_field,
    get_all_users,
    get_user_by_field,
    init_db,
    insert_user,
    insert_user_list,
)


def is_user_admin(field: str, value: str, is_sensitive: bool = False) -> bool:
    """
    Check whether the user has the admin flag.

    Args:
        field: Lookup column.
        value: Value to compare.
        is_sensitive: Whether the field is encrypted in the database.

    Returns:
        True if the user exists and admin=1; False otherwise.
    """
    user = get_user_by_field(field, value, is_sensitive)
    if user is None:
        return False
    return bool(user.get("admin", False))


__all__ = [
    "DB_PATH",
    "init_db",
    "insert_user",
    "insert_user_list",
    "get_user_by_field",
    "find_user_by_prompt",
    "delete_user_by_field",
    "get_all_users",
    "is_user_admin",
]
