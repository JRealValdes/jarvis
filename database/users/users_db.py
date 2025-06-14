import sqlite3
import os
from utils.security import hash_string
from config import DB_DEBUG_MODE
from pathlib import Path
import re

# Define the database path relative to the script's directory
BASE_DIR = Path(__file__).resolve().parents[2]  # goes up from db/users/
DB_PATH = os.path.join(BASE_DIR, 'data', 'users.db')

def init_db():
    """Initialize the database, and create the table in case it doesn't already exist."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                real_name TEXT NOT NULL UNIQUE,
                access_name TEXT NOT NULL UNIQUE,
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
    admin: bool = False
):
    """Insert a new user into the database."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (
                    real_name, access_name, jarvis_name, is_female, admin
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                real_name,
                hash_string(access_name),
                jarvis_name,
                int(is_female),
                int(admin)
            ))
            conn.commit()
    except sqlite3.IntegrityError:
        print(f"[Warning] IntegrityError: User with real_name '{real_name}' or access_name '{access_name}' already exists.")

def insert_user_list(user_list: list[dict]):
    """
    Insert multiple users into the database using the insert_user function.

    Each dictionary in the list must contain the keys:
    - real_name (str)
    - access_name (str)
    - jarvis_name (str)
    - is_female (bool)
    - admin (bool, optional)
    """
    for user in user_list:
        try:
            insert_user(
                real_name=user["real_name"],
                access_name=user["access_name"],
                jarvis_name=user["jarvis_name"],
                is_female=user["is_female"],
                admin=user.get("admin", False)
            )
        except KeyError as e:
            print(f"[Error] Missing required field: {e} in user data: {user}")


def get_user_by_field(field: str, value: str, is_sensitive: bool = False) -> dict | None:
    """
    Returns a user record as a dictionary based on the given field.
    
    Parameters:
    - field: The column to query by ('real_name' or 'access_name').
    - value: The value to match (plaintext; will be hashed if is_sensitive is True).
    - is_sensitive: Whether to hash the value before querying (e.g., for access_name).
    """
    if field not in {"real_name", "access_name"}:
        raise ValueError(f"Field '{field}' is not allowed for querying.")

    actual_value = hash_string(value) if is_sensitive else value

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        query = f"SELECT * FROM users WHERE {field} = ?"
        cursor.execute(query, (actual_value,))
        user = cursor.fetchone()
        return dict(user) if user else None

def find_user_by_prompt(prompt: str) -> str | None:
    """
    Searches for a valid identifier within the prompt 
    (in Spanish: looks for phrases like 'soy Verkk')
    and returns the registered name for Jarvis if found.
    """
    match = re.search(r"\bsoy\s+([^\s,.!?]+)", prompt, re.IGNORECASE)
    if not match:
        return None

    access_candidate = match.group(1).strip().lower()
    user = get_user_by_field("access_name", access_candidate, is_sensitive=True)
    return user

def delete_user_by_field(field: str, value: str, is_sensitive: bool = False) -> bool:
    """
    Delete a user by the value of one of their fields.
    
    Parameters:
    - field: The column to match ('real_name' or 'access_name').
    - value: The value to match (plaintext; will be hashed if is_sensitive is True).
    - is_sensitive: If True, the value will be hashed (e.g., for access_name).
    """
    if field not in {"real_name", "access_name"}:
        raise ValueError(f"Field '{field}' not allowed for deletion.")
    
    actual_value = hash_string(value) if is_sensitive else value

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        query = f"DELETE FROM users WHERE {field} = ?"
        cursor.execute(query, (actual_value,))
        conn.commit()
        return cursor.rowcount > 0

def get_all_users() -> list[tuple]:
    """
    Return all users in the database (for debugging only).
    WARNING: Should not be exposed in production.
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

def is_user_admin(access_name: str) -> bool:
    """Check if a user has admin privileges based on their plaintext access_name."""
    hashed_name = hash_string(access_name)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT admin FROM users WHERE access_name = ?", (hashed_name,))
        result = cursor.fetchone()
        return bool(result[0]) if result else False
