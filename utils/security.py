"""Utilidades de cifrado simétrico (Fernet) y hashing para datos de usuario."""

import hashlib
import os

from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()
FERNET_KEY: str | None = os.getenv("FERNET_KEY")
fernet = Fernet(FERNET_KEY)


def hash_string_sha256_lowered(input_string: str) -> str:
    """
    Calcula el hash SHA-256 de una cadena en minúsculas.

    Args:
        input_string: Texto a hashear.

    Returns:
        Hex digest SHA-256 en minúsculas.
    """
    return hashlib.sha256(input_string.lower().encode()).hexdigest()


def encode_symm_crypt_key(input_string: str) -> str:
    """
    Cifra una cadena con Fernet (clave simétrica de entorno).

    Args:
        input_string: Texto en claro.

    Returns:
        Token cifrado como cadena UTF-8.
    """
    return fernet.encrypt(input_string.encode()).decode()


def decode_symm_crypt_key(encoded_string: str) -> str:
    """
    Descifra una cadena previamente cifrada con Fernet.

    Args:
        encoded_string: Token cifrado.

    Returns:
        Texto en claro.

    Raises:
        cryptography.fernet.InvalidToken: Si la clave o el token no son válidos.
    """
    return fernet.decrypt(encoded_string.encode()).decode()


def encode_multiple_strings_sck(strings: list[str]) -> list[str]:
    """
    Cifra una lista de cadenas.

    Args:
        strings: Lista de textos en claro.

    Returns:
        Lista de tokens cifrados, en el mismo orden.
    """
    return [encode_symm_crypt_key(s) for s in strings]


def decode_multiple_strings_sck(encoded_strings: list[str]) -> list[str]:
    """
    Descifra una lista de tokens Fernet.

    Args:
        encoded_strings: Lista de tokens cifrados.

    Returns:
        Lista de textos en claro, en el mismo orden.
    """
    return [decode_symm_crypt_key(s) for s in encoded_strings]
