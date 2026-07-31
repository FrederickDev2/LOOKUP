"""Server-side session store with idle + absolute-lifetime expiration.

The signed cookie holds only an opaque session id; all expiry state lives in the
`sessions` table, so a user cannot extend a session by editing the cookie.

  * Idle timeout (sliding): a session expires after `SESSION_IDLE_TIMEOUT_MINUTES`
    with no activity. Every validated request refreshes `last_active_at`.
  * Absolute lifetime: a session expires `SESSION_MAX_LIFETIME_HOURS` after it was
    created, no matter how active it is (`created_at` is never moved).
"""
from __future__ import annotations

import secrets
import time
from typing import Optional

from .config import settings
from .database import get_conn


def _now() -> int:
    return int(time.time())


def create_session(user_id: Optional[int], username: str) -> str:
    """Create a new server-side session and return its id. Prunes stale rows."""
    sid = secrets.token_urlsafe(32)
    now = _now()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (id, username, user_id, created_at, last_active_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (sid, username, user_id, now, now),
        )
        conn.commit()
    cleanup()
    return sid


def cleanup() -> None:
    """Delete sessions older than the absolute max lifetime (housekeeping)."""
    cutoff = _now() - settings.session_max_lifetime
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE created_at < ?", (cutoff,))
        conn.commit()


def get(sid: Optional[str]) -> Optional[dict]:
    if not sid:
        return None
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    if not row:
        return None
    return {"username": row["username"], "user_id": row["user_id"],
            "created_at": int(row["created_at"])}


def end_session(sid: Optional[str]) -> None:
    if not sid:
        return
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE id=?", (sid,))
        conn.commit()


def validate(sid: Optional[str]) -> dict:
    """Validate and slide a session.

    Returns one of:
      {"status": "ok", "user_id", "username", "created_at"}   — valid; idle timer refreshed
      {"status": "expired", "reason", "username", "created_at"} — expired; row deleted
      {"status": "missing"}                                    — no such session
    """
    if not sid:
        return {"status": "missing"}
    now = _now()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
        if not row:
            return {"status": "missing"}
        created = int(row["created_at"])
        last_active = int(row["last_active_at"])

        reason = None
        if now - created >= settings.session_max_lifetime:
            reason = "max_lifetime"
        elif now - last_active >= settings.session_idle_timeout:
            reason = "idle"

        if reason:
            conn.execute("DELETE FROM sessions WHERE id=?", (sid,))
            conn.commit()
            return {"status": "expired", "reason": reason,
                    "username": row["username"], "created_at": created}

        # Valid — slide the idle timer (absolute lifetime anchor untouched).
        conn.execute("UPDATE sessions SET last_active_at=? WHERE id=?", (now, sid))
        conn.commit()
        return {"status": "ok", "user_id": row["user_id"],
                "username": row["username"], "created_at": created}
