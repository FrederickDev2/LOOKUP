"""Bulk-lookup file handling: parse an uploaded list, preview columns, and
build downloadable result exports (CSV / Excel).

The uploaded list file is small (a single column of NIA numbers) so pandas is
used directly here. A short-lived token ties the preview step to the run step
and to the generated export files, all kept under the configured temp dir.
"""
from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from .config import settings

ALLOWED_EXTS = {".csv", ".xlsx"}


def _meta_path(token: str) -> Path:
    return settings.tmp_dir / f"{token}.json"


def new_token() -> str:
    return secrets.token_hex(16)


def save_upload_meta(token: str, original_name: str, ext: str, stored_path: Path) -> None:
    _meta_path(token).write_text(
        json.dumps({"original_name": original_name, "ext": ext, "path": str(stored_path)}),
        encoding="utf-8",
    )


def load_upload_meta(token: str) -> Optional[dict]:
    p = _meta_path(token)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None


def preview(path: str, ext: str, n: int = 8) -> Tuple[List[str], List[List[str]]]:
    """Return (column_names, sample_rows) from the top of the file."""
    if ext == ".csv":
        df = pd.read_csv(path, dtype=str, nrows=n, keep_default_na=False)
    else:
        df = pd.read_excel(path, dtype=str, nrows=n, engine="openpyxl")
    df = df.fillna("").astype(str)
    columns = [str(c) for c in df.columns]
    rows = df.values.tolist()
    return columns, rows


def extract_nia_from_file(path: str, ext: str) -> List[str]:
    """Read the NIA column from an uploaded list, auto-detecting which column.

    Prefers a column whose header mentions NIA / Ghana / card; otherwise uses
    the first column. Returns the trimmed, non-empty values in order.
    """
    if ext == ".csv":
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
    else:
        df = pd.read_excel(path, dtype=str, engine="openpyxl")
    df = df.fillna("").astype(str)
    cols = [str(c) for c in df.columns]
    if not cols:
        return []
    chosen = None
    for c in cols:
        k = c.strip().upper()
        if "NIA" in k or "GHANA" in k or "CARD" in k:
            chosen = c
            break
    if chosen is None:
        chosen = cols[0]
    return [str(v).strip() for v in df[chosen].tolist() if str(v).strip()]


def read_column_values(path: str, ext: str, column: str) -> List[str]:
    """Read every value from the chosen column as strings."""
    if ext == ".csv":
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
    else:
        df = pd.read_excel(path, dtype=str, engine="openpyxl")
    df = df.fillna("").astype(str)
    if column not in df.columns:
        raise ValueError(f"Column '{column}' not found in the file.")
    return [str(v).strip() for v in df[column].tolist()]


def build_exports(token: str, headers: List[str], result_rows: List[Dict[str, str]]) -> None:
    """Write CSV and XLSX exports for the result set under the token."""
    df = pd.DataFrame(result_rows, columns=headers)
    df.to_csv(settings.tmp_dir / f"{token}_results.csv", index=False)
    df.to_excel(settings.tmp_dir / f"{token}_results.xlsx", index=False, engine="openpyxl")


def export_path(token: str, fmt: str) -> Optional[Path]:
    fmt = fmt.lower()
    if fmt not in {"csv", "xlsx"}:
        return None
    p = settings.tmp_dir / f"{token}_results.{fmt}"
    return p if p.exists() else None
