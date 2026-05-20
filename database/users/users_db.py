"""
Acceso a usuarios — capa de compatibilidad.

El código nuevo debe usar:
- ``infrastructure.persistence.users.repository`` para SQL
- ``domain.users.identification`` para identificación por prompt
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
