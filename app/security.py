"""Password hashing helpers (bcrypt).

Passwords are only ever stored as bcrypt hashes. Plaintext passwords are used
transiently to hash / verify and are never persisted or logged.
"""
from __future__ import annotations

import bcrypt

# bcrypt only considers the first 72 bytes of the password.
_MAX_BYTES = 72


def _encode(password: str) -> bytes:
    return password.encode("utf-8")[:_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_encode(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(_encode(password), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False
