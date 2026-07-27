"""Member lookup by normalized NIA number."""
from __future__ import annotations

import json
from typing import Dict, List, Optional

from .database import get_conn


def single_lookup(normalized_nia: str) -> Optional[Dict[str, str]]:
    """Return the member record (as a dict of header -> value) or None.

    The raw salary field remains in the returned dict; callers must strip it
    for display/export via columns.display_fields / columns.export_headers.
    """
    if not normalized_nia:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT data_json FROM members WHERE nia_normalized=? LIMIT 1",
            (normalized_nia,),
        ).fetchone()
    if not row:
        return None
    return json.loads(row["data_json"])


def bulk_lookup(normalized_list: List[str]) -> List[Optional[Dict[str, str]]]:
    """Look up each normalized NIA, preserving input order and duplicates.

    Returns a list the same length as the input; each element is the matched
    record dict or None if not found.
    """
    if not normalized_list:
        return []

    # Fetch all distinct matches in one pass, then map back to input order.
    distinct = {n for n in normalized_list if n}
    found: Dict[str, Dict[str, str]] = {}
    if distinct:
        with get_conn() as conn:
            # Query in chunks to keep the SQL parameter list bounded.
            values = list(distinct)
            for start in range(0, len(values), 900):
                chunk = values[start:start + 900]
                placeholders = ",".join("?" * len(chunk))
                rows = conn.execute(
                    f"SELECT nia_normalized, data_json FROM members "
                    f"WHERE nia_normalized IN ({placeholders})",
                    chunk,
                ).fetchall()
                for r in rows:
                    # First match wins if duplicates exist in the dataset.
                    found.setdefault(r["nia_normalized"], json.loads(r["data_json"]))

    return [found.get(n) if n else None for n in normalized_list]
