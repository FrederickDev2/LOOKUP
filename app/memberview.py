"""Build the grouped, display-ready view of a member record for the lookup page.

Groups fields into Identity / Contact / Employment / Scheme panels, formats
dates, derives age / tenure / gender label, and drops blank rows (so empty
columns like the SSNIT SSNO 1-5 never show). Monthly salary is never included.
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Dict, List, Optional

from .columns import build_full_name, initials

_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _g(rec: Dict[str, str], key: str) -> str:
    return (rec.get(key) or "").strip()


def _fmt_date(s: str) -> str:
    """Render an ISO date (YYYY-MM-DD...) as '21 Jul 1982'; pass other text through."""
    s = (s or "").strip()
    m = _ISO.match(s)
    if not m:
        return s
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if 1 <= mo <= 12:
        return f"{d} {_MONTHS[mo - 1]} {y}"
    return s


def _years_since(s: str) -> Optional[int]:
    m = _ISO.match((s or "").strip())
    if not m:
        return None
    try:
        d = _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    today = _dt.date.today()
    y = today.year - d.year - ((today.month, today.day) < (d.month, d.day))
    return y if 0 <= y < 150 else None


def _gender_label(g: str) -> str:
    u = (g or "").strip().upper()
    if u in ("M", "MALE"):
        return "Male"
    if u in ("F", "FEMALE"):
        return "Female"
    return (g or "").strip()


def _panel(title: str, rows: List[tuple]) -> Optional[dict]:
    """rows: list of (label, value, mono_bool). Drops blanks; None if all blank."""
    kept = [{"label": lbl, "value": val, "mono": mono}
            for (lbl, val, mono) in rows if (val or "").strip()]
    return {"title": title, "rows": kept} if kept else None


def build_member_view(record: Dict[str, str], normalized: str = "") -> dict:
    full_name = build_full_name(record)
    dob = _g(record, "DOB")
    joined = _g(record, "DATE JOINED SCHEME")
    age = _years_since(dob)
    tenure = _years_since(joined)
    gender_label = _gender_label(_g(record, "GENDER"))
    status = _g(record, "CONTRIBUTION STATUS")
    current_employer = _g(record, "EERNO CURRENT NAME") or _g(record, "NAME OF EMPLOYER")

    panels: List[dict] = []
    for title, rows in (
        ("Identity", [
            ("SSNIT no.", _g(record, "SSNIT SSNO"), True),
            ("SSNIT reference", _g(record, "SSNIT REFERENCE NUMBER"), True),
            ("Previous name", _g(record, "PREVIOUS NAME"), False),
            ("Date of birth", _fmt_date(dob), False),
            ("Gender", gender_label, False),
            ("Nationality", _g(record, "NATIONALITY"), False),
        ]),
        ("Contact", [
            ("Telephone", _g(record, "TELEPHONE NUMBER"), True),
            ("Email", _g(record, "EMAIL ADDRESS"), False),
            ("Permanent address", _g(record, "PERMANENT ADDRESS"), False),
        ]),
        ("Employment", [
            ("Current employer", _g(record, "EERNO CURRENT NAME"), False),
            ("Current EER no.", _g(record, "EERNO CURRENT"), True),
            ("Previous employer", _g(record, "NAME OF EMPLOYER"), False),
            ("Previous EER no.", _g(record, "EERNO"), True),
            ("Nature of employment", _g(record, "NATURE OF EMPLOYMENT"), False),
            ("Nature of job", _g(record, "NATURE OF JOB"), False),
        ]),
        ("Scheme", [
            ("Date joined", _fmt_date(joined), False),
            ("Years on scheme", f"{tenure} years" if tenure is not None else "", False),
            ("Date of retirement", _fmt_date(_g(record, "DATE OF RETIREMENT")), False),
            ("Sector", _g(record, "TYPE OF SECTOR"), False),
            ("Nature of income", _g(record, "NATURE OF INCOME"), False),
            ("Contribution status", status, False),
        ]),
    ):
        p = _panel(title, rows)
        if p:
            panels.append(p)

    # "Male · 43 yrs" meta pill (whichever parts are known).
    if gender_label and age is not None:
        meta = f"{gender_label} · {age} yrs"
    elif gender_label:
        meta = gender_label
    elif age is not None:
        meta = f"{age} yrs"
    else:
        meta = ""

    return {
        "name": full_name or "Member record",
        "initials": initials(full_name),
        "nia": _g(record, "NIA NUMBER") or normalized,
        "meta": meta,
        "status": status,
        "current_employer": current_employer,
        "panels": panels,
    }
