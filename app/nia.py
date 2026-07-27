"""Ghana Card / NIA number normalization and validation.

Normalization rule (applied identically on import and on lookup):
    strip all hyphens and whitespace, then uppercase.

A Ghana Card number looks like "GHA-001849879-4", i.e. the prefix "GHA"
followed by 9 digits and a single check digit. Normalized it becomes
"GHA0018498794" -> "GHA" + 10 digits.
"""
from __future__ import annotations

import re

_STRIP_RE = re.compile(r"[\s\-]+")
# Normalized canonical form: GHA + 10 digits.
_VALID_RE = re.compile(r"^GHA\d{10}$")


def normalize_nia(raw: object) -> str:
    """Normalize a raw NIA value to its canonical comparison form.

    Removes every hyphen and whitespace character, then uppercases.
    Returns "" for None / empty input.
    """
    if raw is None:
        return ""
    text = str(raw).strip()
    if not text:
        return ""
    return _STRIP_RE.sub("", text).upper()


def is_valid_nia(normalized: str) -> bool:
    """Return True if the normalized value matches the Ghana Card format."""
    return bool(_VALID_RE.match(normalized or ""))


def format_hint() -> str:
    return (
        "Expected a Ghana Card number like GHA-001849879-4 "
        "(prefix GHA followed by 10 digits). Hyphens and spaces are optional."
    )
