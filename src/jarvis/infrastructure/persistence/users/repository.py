"""SQLite user repository (data access only, no business rules)."""

import logging
import os
import sqlite3
logger = logging.getLogger(__name__)

from jarvis.core.config import DB_DEBUG_MODE
from jarvis.core.paths import USERS_DB_PATH
from jarvis.infrastructure.crypto.fernet import decode_symm_crypt_key, encode_symm_crypt_key

DB_PATH = str(USERS_DB_PATH)

_ALLOWED_QUERY_FIELDS = frozenset({"real_name", "access_name"})


def init_db() -> None:
    """
    Create the database and ``users`` table if they do not exist.

    Returns:
        None.
    """
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                real_name TEXT NOT NULL UNIQUE,
                access_name TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                jarvis_name TEXT NOT NULL,
                is_female BOOLEAN NOT NULL,
                admin BOOLEAN NOT NULL DEFAULT 0
            )
        """)
        conn.commit()


def insert_user(
    real_name: str,
    access_name: str,
    jarvis_name: str,
    is_female: bool,
    password: str,
    admin: bool = False,
) -> None:
    """
    Insert a user; encrypt access_name and password.

    Args:
        real_name: Unique real name.
        access_name: Login name (stored encrypted).
        jarvis_name: Name Jarvis uses when addressing the user.
        is_female: True if the user is female.
        password: Plain-text password (stored encrypted).
        admin: Administrator privileges.

    Returns:
        None. Prints a warning on IntegrityError (duplicate).
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (
                    real_name, access_name, password, jarvis_name, is_female, admin
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                real_name,
                encode_symm_crypt_key(access_name),
                encode_symm_crypt_key(password),
                jarvis_name,
                int(is_female),
                int(admin),
            ))
            conn.commit()
    except sqlite3.IntegrityError:
        logger.warning(
            "IntegrityError: user with real_name '%s' or access_name '%s' already exists",
            real_name,
            access_name,
        )


def insert_user_list(user_list: list[dict]) -> None:
    """
    Insert multiple users by calling ``insert_user`` for each dict.

    Args:
        user_list: List of dicts with keys real_name, access_name, password,
            jarvis_name, is_female, and optionally admin.

    Returns:
        None.
    """
    for user in user_list:
        try:
            insert_user(
                real_name=user["real_name"],
                access_name=user["access_name"],
                password=user["password"],
                jarvis_name=user["jarvis_name"],
                is_female=user["is_female"],
                admin=user.get("admin", False),
            )
        except KeyError as e:
            logger.error("Missing required field %s in user data: %s", e, user)


def get_user_by_field(field: str, value: str, is_sensitive: bool = False) -> dict | None:
    """
    Look up a user by column.

    Args:
        field: ``real_name`` or ``access_name``.
        value: Value to compare (plain text; decrypted in DB when is_sensitive).
        is_sensitive: If True, scan rows decrypting (e.g. access_name).

    Returns:
        User row dict or None if no match.

    Raises:
        ValueError: If field is not allowed.
    """
    if field not in _ALLOWED_QUERY_FIELDS:
        raise ValueError(f"Field '{field}' is not allowed for querying.")

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if is_sensitive:
            cursor.execute("SELECT * FROM users")
            rows = cursor.fetchall()
            for row in rows:
                try:
                    decrypted_value = decode_symm_crypt_key(row[field])
                    if decrypted_value == value:
                        return dict(row)
                except Exception as e:
                    logger.error("Decryption failed for %s: %s", field, e)
            return None

        cursor.execute(f"SELECT * FROM users WHERE {field} = ?", (value,))
        row = cursor.fetchone()
        return dict(row) if row else None


def delete_user_by_field(field: str, value: str, is_sensitive: bool = False) -> bool:
    """
    Delete a user located by field.

    Args:
        field: ``real_name`` or ``access_name``.
        value: Value to search for.
        is_sensitive: Whether the field is encrypted in the database.

    Returns:
        True if one row was deleted; False if user not found.

    Raises:
        ValueError: If field is not allowed.
    """
    if field not in _ALLOWED_QUERY_FIELDS:
        raise ValueError(f"Field '{field}' not allowed for deletion.")

    user = get_user_by_field(field, value, is_sensitive)
    if not user:
        return False

    user_id = user["id"]
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return cursor.rowcount > 0


def get_all_users() -> list[tuple]:
    """
    List all users (only when DB_DEBUG_MODE is enabled).

    Returns:
        Rows (id, real_name, access_name, jarvis_name, is_female, admin).

    Raises:
        PermissionError: If DB_DEBUG_MODE is False.
    """
    if not DB_DEBUG_MODE:
        raise PermissionError("Access to user list is disabled in production.")

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, real_name, access_name, jarvis_name, is_female, admin
            FROM users
        """)
        return cursor.fetchall()
