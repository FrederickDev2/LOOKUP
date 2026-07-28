"""Canonical member columns and the salary-exclusion rule.

Member records are stored as a JSON blob keyed by a *normalized header name*
(see header_key). This keeps ingestion flexible: whatever columns exist in the
uploaded Excel file are stored, and display simply iterates a canonical order,
appending any extra columns it did not know about.

MONTHLY SALARY is deliberately excluded from every output path (single lookup,
bulk results and exports).
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

# Header that must never be shown / exported.
SALARY_HEADER = "MONTHLY SALARY"

# The NIA column we key lookups on.
NIA_HEADER = "NIA NUMBER"

# Preferred display order. Any stored column not listed here is appended after
# these, in its original file order.
CANONICAL_COLUMNS: List[str] = [
    "EERNO",
    "NAME OF EMPLOYER",
    "NIA NUMBER",
    "SSNIT SSNO",
    "SSNIT SSNO 1",
    "SSNIT SSNO 2",
    "SSNIT SSNO 3",
    "SSNIT SSNO 4",
    "SSNIT SSNO 5",
    "SSNIT REFERENCE NUMBER",
    "FIRST NAME",
    "OTHER NAMES",
    "LAST NAME",
    "PREVIOUS NAME",
    "DOB",
    "GENDER",
    "NATIONALITY",
    "PERMANENT ADDRESS",
    "TELEPHONE NUMBER",
    "EMAIL ADDRESS",
    "EERNO CURRENT",
    "EERNO CURRENT NAME",
    "DATE JOINED SCHEME",
    "DATE OF RETIREMENT",
    "NATURE OF EMPLOYMENT",
    "TYPE OF SECTOR",
    "NATURE OF INCOME",
    "MONTHLY SALARY",
    "CONTRIBUTION STATUS",
    "NATURE OF JOB",
]

_WS_RE = re.compile(r"\s+")


def header_key(raw: object) -> str:
    """Normalize a column header for consistent matching/storage.

    Collapses internal whitespace, strips ends, and uppercases so that
    "  first  name " and "First Name" both become "FIRST NAME".
    """
    if raw is None:
        return ""
    return _WS_RE.sub(" ", str(raw).strip()).upper()


def is_salary(header: str) -> bool:
    return header_key(header) == SALARY_HEADER


def display_fields(data: Dict[str, str]) -> List[Tuple[str, str]]:
    """Return (label, value) pairs for display, excluding MONTHLY SALARY.

    Canonical columns first (only those present), then any extras in stored
    order.
    """
    out: List[Tuple[str, str]] = []
    seen = set()
    for col in CANONICAL_COLUMNS:
        if is_salary(col):
            continue
        if col in data:
            out.append((col, data.get(col, "") or ""))
            seen.add(col)
    for col, val in data.items():
        if col in seen or is_salary(col):
            continue
        out.append((col, val or ""))
    return out


# Name components combined into the result header (so they aren't repeated in the
# detail grid), plus the NIA which is shown as a pill.
NAME_PARTS = ["FIRST NAME", "OTHER NAMES", "LAST NAME"]
HEADER_FIELDS = set(NAME_PARTS) | {NIA_HEADER}


def build_full_name(record: Dict[str, str]) -> str:
    """Join FIRST/OTHER/LAST name parts into a single display name."""
    parts = [(record.get(p) or "").strip() for p in NAME_PARTS]
    return " ".join(p for p in parts if p)


def initials(full_name: str) -> str:
    """Up to two uppercase initials from a full name (for the avatar)."""
    words = [w for w in (full_name or "").split() if w]
    if not words:
        return "–"
    if len(words) == 1:
        return words[0][0].upper()
    return (words[0][0] + words[-1][0]).upper()


def detail_fields(data: Dict[str, str]) -> List[Tuple[str, str]]:
    """Display fields for the result grid: canonical order, salary excluded,
    name/NIA excluded (shown in the header), and BLANK values omitted.
    """
    out: List[Tuple[str, str]] = []
    for label, value in display_fields(data):
        if label in HEADER_FIELDS:
            continue
        if not (value or "").strip():
            continue
        out.append((label, value))
    return out


def export_headers(sample_keys: List[str]) -> List[str]:
    """Column order used for bulk exports, excluding salary."""
    headers: List[str] = []
    seen = set()
    for col in CANONICAL_COLUMNS:
        if is_salary(col):
            continue
        if col in sample_keys:
            headers.append(col)
            seen.add(col)
    for col in sample_keys:
        if col in seen or is_salary(col):
            continue
        headers.append(col)
    return headers
