import hashlib
from cryptography.fernet import Fernet
from dotenv import load_dotenv
import os

load_dotenv()
FERNET_KEY = os.getenv("FERNET_KEY")
fernet = Fernet(FERNET_KEY)

def hash_string_sha256_lowered(input_string: str) -> str:
    """Returns a SHA-256 hash of the input string (lowercase)"""
    return hashlib.sha256(input_string.lower().encode()).hexdigest()

def encode_symm_crypt_key(input_string: str) -> str:
    """Encodes a string into a symmetric encryption key using Fernet"""
    return fernet.encrypt(input_string.encode()).decode()

def decode_symm_crypt_key(encoded_string: str) -> str:
    """Decodes a symmetric encryption key using Fernet"""
    return fernet.decrypt(encoded_string.encode()).decode()

def encode_multiple_strings_sck(strings: list) -> list:
    """Encodes a list of strings into symmetric encryption keys"""
    return [encode_symm_crypt_key(s) for s in strings]

def decode_multiple_strings_sck(encoded_strings: list) -> list:
    """Decodes a list of symmetric encryption keys back into strings"""
    return [decode_symm_crypt_key(s) for s in encoded_strings]
