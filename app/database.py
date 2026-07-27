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
        _migrate_members_index(conn)


def _migrate_members_index(conn: sqlite3.Connection) -> None:
    """Upgrade a pre-1.1 database that had a non-unique members index.

    Older installs stored blank NIAs as "" with a non-unique index. Convert
    those to NULL and rebuild the index as UNIQUE so upsert imports work. Safe
    no-op on fresh databases (which already have the UNIQUE index).
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name='idx_members_nia'"
    ).fetchone()
    if not row or "UNIQUE" in (row["sql"] or "").upper():
        return
    try:
        conn.execute("UPDATE members SET nia_normalized=NULL WHERE nia_normalized=''")
        conn.execute("DROP INDEX idx_members_nia")
        conn.execute("CREATE UNIQUE INDEX idx_members_nia ON members (nia_normalized)")
        conn.commit()
    except sqlite3.IntegrityError:
        # Duplicate NIA values already exist; leave the DB as-is and warn.
        conn.rollback()
        print("[WARN] Could not create a UNIQUE index on members.nia_normalized "
              "because duplicate NIA values exist. Deduplicate before merge imports.")


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
