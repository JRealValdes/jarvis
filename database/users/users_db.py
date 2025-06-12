import sqlite3
import os
from utils.security import hash_string
from config import DB_DEBUG_MODE
from pathlib import Path

# Define the database path relative to the script's directory
BASE_DIR = Path(__file__).resolve().parents[2]  # sube desde db/users/
DB_PATH = os.path.join(BASE_DIR, 'data', 'users.db')

def init_db():
    """Initialize the database, and create the table in case it doesn't already exist."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                identification TEXT NOT NULL UNIQUE,
                jarvis_registered_name TEXT NOT NULL
            )
        """)
        conn.commit()

def insert_user(username: str, identification: str, jarvis_registered_name: str):
    """Insert a new user into the database."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (username, identification, jarvis_registered_name)
                VALUES (?, ?, ?)
            """, (username, hash_string(identification), jarvis_registered_name))
            conn.commit()
    except sqlite3.IntegrityError:
        print(f"[Warning] Identification already exists for user: {username}")

def find_registered_name_by_hashed_id(hashed_user_id: str) -> str | None:
    """Find the registered name of a user based on their hashed identification."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT jarvis_registered_name FROM users WHERE identification = ?", (hashed_user_id,))
        result = cursor.fetchone()
        return result[0] if result else None

def find_registered_name_by_prompt(prompt: str) -> str | None:
    """
    Searches for a valid identifier within the prompt 
    (in Spanish: looks for phrases like 'soy Verkk')
    and returns the registered name for Jarvis if found.
    """
    import re

    # Looks for "soy <identificador>" or "Soy <identificador>"
    match = re.search(r"\bsoy\s+([^\s,.!?]+)", prompt, re.IGNORECASE)
    if not match:
        return None

    identification_candidate = match.group(1).strip().lower()
    hashed_user_id = hash_string(identification_candidate)
    return find_registered_name_by_hashed_id(hashed_user_id)

def delete_user_by_username(username: str) -> bool:
    """Delete a user from the database by username."""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()
        return cursor.rowcount > 0

def delete_user_by_identification(identification: str) -> bool:
    """Delete a user by their plaintext identification string."""
    hashed_id = hash_string(identification)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE identification = ?", (hashed_id,))
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
        cursor.execute("SELECT id, username, identification, jarvis_registered_name FROM users")
        return cursor.fetchall()
