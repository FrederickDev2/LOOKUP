"""Audit logging for queries and imports (admin-visible only).

Privacy rule: for queries we store WHO searched, WHAT normalized NIA number(s)
were searched, and WHEN — never the result of the search.
"""
from __future__ import annotations

import json
from typing import List

from .database import get_conn, utcnow_iso


def log_single_query(username: str, normalized_nia: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO query_logs (username, query_type, query_value, item_count, created_at) "
            "VALUES (?, 'single', ?, 1, ?)",
            (username, normalized_nia, utcnow_iso()),
        )
        conn.commit()


def log_bulk_query(username: str, normalized_list: List[str]) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO query_logs (username, query_type, query_value, item_count, created_at) "
            "VALUES (?, 'bulk', ?, ?, ?)",
            (username, json.dumps(normalized_list), len(normalized_list), utcnow_iso()),
        )
        conn.commit()


def log_import(filename: str, row_count: int, skipped_count: int,
               imported_by: str, status: str, message: str = "") -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO import_logs "
            "(filename, row_count, skipped_count, imported_by, imported_at, status, message) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (filename, row_count, skipped_count, imported_by, utcnow_iso(), status, message),
        )
        conn.commit()


def recent_query_logs(limit: int = 200):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM query_logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()


def recent_import_logs(limit: int = 100):
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM import_logs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
