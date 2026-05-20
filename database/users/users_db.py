"""Acceso SQLite a la tabla de usuarios (credenciales cifradas con Fernet)."""

import os
import re
import sqlite3
from pathlib import Path

from utils.security import encode_symm_crypt_key, decode_symm_crypt_key
from config import DB_DEBUG_MODE

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = os.path.join(BASE_DIR, "data", "users.db")


def init_db() -> None:
    """
    Crea la base de datos y la tabla ``users`` si no existen.

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
    Inserta un usuario; cifra access_name y password.

    Args:
        real_name: Nombre real único.
        access_name: Nombre de acceso (se cifra en BD).
        jarvis_name: Nombre con el que Jarvis se dirige al usuario.
        is_female: True si el usuario es mujer.
        password: Contraseña en claro (se cifra en BD).
        admin: Privilegios de administrador.

    Returns:
        None. Imprime aviso si hay IntegrityError (duplicado).
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
        print(
            f"[Warning] IntegrityError: User with real_name '{real_name}' "
            f"or access_name '{access_name}' already exists."
        )


def insert_user_list(user_list: list[dict]) -> None:
    """
    Inserta varios usuarios llamando a ``insert_user`` por cada dict.

    Args:
        user_list: Lista de dicts con claves real_name, access_name, password,
            jarvis_name, is_female y opcionalmente admin.

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
            print(f"[Error] Missing required field: {e} in user data: {user}")


def get_user_by_field(field: str, value: str, is_sensitive: bool = False) -> dict | None:
    """
    Busca un usuario por columna.

    Args:
        field: ``real_name`` o ``access_name``.
        value: Valor a comparar (en claro; se descifra en BD si is_sensitive).
        is_sensitive: Si True, recorre filas descifrando (p. ej. access_name).

    Returns:
        Dict con fila de usuario o None si no hay coincidencia.

    Raises:
        ValueError: Si field no está permitido.
    """
    if field not in {"real_name", "access_name"}:
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
                    print(f"[Error] Decryption failed for {field}: {e}")
            return None

        cursor.execute(f"SELECT * FROM users WHERE {field} = ?", (value,))
        row = cursor.fetchone()
        return dict(row) if row else None


def find_user_by_prompt(prompt: str) -> dict | None:
    """
    Detecta ``soy <nombre>`` en el prompt y busca usuario por access_name.

    Args:
        prompt: Texto libre del usuario.

    Returns:
        Dict de usuario si existe; None si no hay patrón o no hay match.
    """
    match = re.search(r"\bsoy\s+([^\s,.!?]+)", prompt, re.IGNORECASE)
    if not match:
        return None

    access_candidate = match.group(1).strip()
    return get_user_by_field("access_name", access_candidate, is_sensitive=True)


def delete_user_by_field(field: str, value: str, is_sensitive: bool = False) -> bool:
    """
    Elimina un usuario localizado por campo.

    Args:
        field: ``real_name`` o ``access_name``.
        value: Valor a buscar.
        is_sensitive: Si el campo está cifrado en BD.

    Returns:
        True si se eliminó una fila; False si no se encontró usuario.

    Raises:
        ValueError: Si field no está permitido.
    """
    if field not in {"real_name", "access_name"}:
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
    Lista todos los usuarios (solo si DB_DEBUG_MODE está activo).

    Returns:
        Filas (id, real_name, access_name, jarvis_name, is_female, admin).

    Raises:
        PermissionError: Si DB_DEBUG_MODE es False.
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


def is_user_admin(field: str, value: str, is_sensitive: bool = False) -> bool:
    """
    Comprueba si el usuario tiene flag admin.

    Args:
        field: Columna de búsqueda.
        value: Valor a comparar.
        is_sensitive: Si el campo está cifrado.

    Returns:
        True si el usuario existe y admin=1; False en caso contrario.
    """
    user = get_user_by_field(field, value, is_sensitive)
    if user is None:
        return False
    return bool(user.get("admin", False))
