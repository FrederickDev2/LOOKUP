"""SQLite access layer and schema.

A fresh connection is opened per operation (SQLite handles this well at this
scale and it sidesteps cross-thread connection issues under the FastAPI
threadpool). WAL mode + a busy timeout keep reads responsive during an import.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional

from .config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('admin', 'user')),
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL,
    created_by    TEXT
);

CREATE TABLE IF NOT EXISTS members (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    nia_normalized TEXT,               -- NULL for rows that have no NIA number
    nia_original   TEXT,
    data_json      TEXT NOT NULL
);
-- UNIQUE so imports can upsert on the NIA. SQLite treats NULLs as distinct,
-- so multiple rows without a NIA are allowed.
CREATE UNIQUE INDEX IF NOT EXISTS idx_members_nia ON members (nia_normalized);

CREATE TABLE IF NOT EXISTS import_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    filename     TEXT,
    row_count    INTEGER,
    skipped_count INTEGER,
    imported_by  TEXT,
    imported_at  TEXT NOT NULL,
    status       TEXT NOT NULL,
    message      TEXT
);

CREATE TABLE IF NOT EXISTS query_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT,
    query_type  TEXT NOT NULL,       -- 'single' | 'bulk'
    query_value TEXT,                -- normalized NIA (single) or JSON list (bulk)
    item_count  INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- Server-side session store (so expiry can't be bypassed by editing the cookie).
CREATE TABLE IF NOT EXISTS sessions (
    id             TEXT PRIMARY KEY,     -- random session id (stored in the cookie)
    username       TEXT NOT NULL,
    user_id        INTEGER,
    created_at     INTEGER NOT NULL,     -- epoch seconds (absolute-lifetime anchor)
    last_active_at INTEGER NOT NULL      -- epoch seconds (sliding idle anchor)
);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions (created_at);

-- Session lifecycle audit (expiry / logout), admin-visible.
CREATE TABLE IF NOT EXISTS session_logs (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    username           TEXT,
    session_started_at TEXT,             -- ISO
    expired_at         TEXT NOT NULL,    -- ISO
    reason             TEXT NOT NULL,    -- 'idle' | 'max_lifetime' | 'logout'
    created_at         TEXT NOT NULL
);
"""


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(settings.db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    settings.ensure_dirs()
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        conn.commit()
        try:
            removed = ensure_unique_nia_index(conn)
            conn.commit()
            if removed:
                print(f"[migrate] Rebuilt a UNIQUE index on members.nia_normalized; "
                      f"removed {removed} older duplicate-NIA row(s).")
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            print(f"[WARN] Could not build the UNIQUE index on members.nia_normalized: {exc}")


def ensure_unique_nia_index(conn: sqlite3.Connection) -> int:
    """Guarantee a UNIQUE index on members.nia_normalized.

    Fresh databases already have it (created by SCHEMA). Older ones had a
    NON-unique index and may contain blank ("") keys and/or duplicate NIA rows
    left by the previous replace-mode importer. To make upsert imports possible
    we:
      * convert blank keys to NULL (SQLite keeps NULLs distinct), and
      * collapse duplicate NIAs, keeping the most recently inserted row (max id),
    then rebuild the index as UNIQUE.

    Idempotent: returns immediately if the index is already UNIQUE. Returns the
    number of duplicate rows removed. The caller owns the transaction/commit.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_members_nia'"
    ).fetchone()
    if row and "UNIQUE" in (row["sql"] or "").upper():
        return 0

    conn.execute("UPDATE members SET nia_normalized=NULL WHERE nia_normalized=''")
    cur = conn.execute(
        "DELETE FROM members "
        "WHERE nia_normalized IS NOT NULL AND id NOT IN ("
        "  SELECT MAX(id) FROM members WHERE nia_normalized IS NOT NULL "
        "  GROUP BY nia_normalized"
        ")"
    )
    removed = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    if row:
        conn.execute("DROP INDEX idx_members_nia")
    conn.execute("CREATE UNIQUE INDEX idx_members_nia ON members (nia_normalized)")
    return removed


# --- meta helpers -----------------------------------------------------------

def set_meta(key: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        conn.commit()


def get_meta(key: str) -> Optional[str]:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None
