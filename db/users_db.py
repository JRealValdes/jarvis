import sqlite3
import re
from pathlib import Path

DB_PATH = Path(__file__).parent / "data/secret_users.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT NOT NULL,
            identification TEXT NOT NULL,
            jarvis_registered_name TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def insert_user(username: str, identification: str, jarvis_registered_name: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO users (username, identification, jarvis_registered_name)
        VALUES (?, ?, ?)
    """, (username, identification, jarvis_registered_name))
    conn.commit()
    conn.close()

def find_registered_name_by_identification(user_input: str) -> str | None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT identification, jarvis_registered_name FROM users")
    rows = cursor.fetchall()
    conn.close()

    user_input_lower = user_input.lower()

    for identification, jarvis_registered_name in rows:
        pattern = rf"\bsoy\s+{re.escape(identification.lower())}\b"
        if re.search(pattern, user_input_lower):
            return jarvis_registered_name

    return None
