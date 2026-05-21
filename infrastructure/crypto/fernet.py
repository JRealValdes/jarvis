"""Symmetric encryption (Fernet) and hashing utilities for user data."""

import hashlib
import os

from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv()
FERNET_KEY: str | None = os.getenv("FERNET_KEY")
fernet = Fernet(FERNET_KEY)


def hash_string_sha256_lowered(input_string: str) -> str:
    """
    Compute the SHA-256 hash of a lowercased string.

    Args:
        input_string: Text to hash.

    Returns:
        Lowercase SHA-256 hex digest.
    """
    return hashlib.sha256(input_string.lower().encode()).hexdigest()


def encode_symm_crypt_key(input_string: str) -> str:
    """
    Encrypt a string with Fernet (symmetric key from environment).

    Args:
        input_string: Plain text.

    Returns:
        Encrypted token as a UTF-8 string.
    """
    return fernet.encrypt(input_string.encode()).decode()


def decode_symm_crypt_key(encoded_string: str) -> str:
    """
    Decrypt a string previously encrypted with Fernet.

    Args:
        encoded_string: Encrypted token.

    Returns:
        Plain text.

    Raises:
        cryptography.fernet.InvalidToken: If the key or token is invalid.
    """
    return fernet.decrypt(encoded_string.encode()).decode()


def encode_multiple_strings_sck(strings: list[str]) -> list[str]:
    """
    Encrypt a list of strings.

    Args:
        strings: List of plain texts.

    Returns:
        List of encrypted tokens in the same order.
    """
    return [encode_symm_crypt_key(s) for s in strings]


def decode_multiple_strings_sck(encoded_strings: list[str]) -> list[str]:
    """
    Decrypt a list of Fernet tokens.

    Args:
        encoded_strings: List of encrypted tokens.

    Returns:
        List of plain texts in the same order.
    """
    return [decode_symm_crypt_key(s) for s in encoded_strings]
