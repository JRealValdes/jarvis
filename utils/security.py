import hashlib

def hash_string(input_string: str) -> str:
    """Returns a SHA-256 hash of the input string (lowercase)"""
    return hashlib.sha256(input_string.lower().encode()).hexdigest()
