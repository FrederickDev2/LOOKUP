"""User account management (multi-account from the start).

Backed by the `users` table. The app ships with two seeded accounts (one admin,
one shared query account) but admins can create/disable more at runtime with no
code changes.
"""
from __future__ import annotations

import sqlite3
from typing import List, Optional

from .database import get_conn, utcnow_iso
from .security import hash_password, verify_password

VALID_ROLES = {"admin", "user"}


def create_user(username: str, password: str, role: str, created_by: str = "system") -> None:
    username = (username or "").strip()
    if not username:
        raise ValueError("Username is required.")
    if role not in VALID_ROLES:
        raise ValueError(f"Role must be one of {sorted(VALID_ROLES)}.")
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    with get_conn() as conn:
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash, role, is_active, created_at, created_by) "
                "VALUES (?, ?, ?, 1, ?, ?)",
                (username, hash_password(password), role, utcnow_iso(), created_by),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"A user named '{username}' already exists.") from exc


def upsert_seed_user(username: str, password: str, role: str) -> str:
    """Create the user if missing. Returns 'created' or 'exists'.

    Used by the first-run seed script; it never overwrites an existing account's
    password.
    """
    if get_by_username(username):
        return "exists"
    create_user(username, password, role, created_by="seed")
    return "created"


def get_by_username(username: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE username=?", ((username or "").strip(),)
        ).fetchone()


def get_by_id(user_id: int) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()


def list_users() -> List[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users ORDER BY role DESC, username ASC"
        ).fetchall()


def authenticate(username: str, password: str) -> Optional[sqlite3.Row]:
    """Return the user row on success, else None. Disabled users cannot log in."""
    user = get_by_username(username)
    if not user or not user["is_active"]:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def set_active(user_id: int, active: bool) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE users SET is_active=? WHERE id=?", (1 if active else 0, user_id))
        conn.commit()


def set_password(user_id: int, new_password: str) -> None:
    if not new_password or len(new_password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET password_hash=? WHERE id=?",
            (hash_password(new_password), user_id),
        )
        conn.commit()


def count_active_admins(exclude_id: Optional[int] = None) -> int:
    with get_conn() as conn:
        if exclude_id is None:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM users WHERE role='admin' AND is_active=1"
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM users WHERE role='admin' AND is_active=1 AND id<>?",
                (exclude_id,),
            ).fetchone()
        return row["c"]
