#!/usr/bin/env python3
"""Generate a small sample .xlsx dataset for testing the import + lookup flow.

Creates ./sample/sample_members.xlsx with the expected columns and a handful of
synthetic (fake) member rows. No real PII.

Usage:
    python scripts/make_sample_data.py
"""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from app.columns import CANONICAL_COLUMNS

ROWS = [
    {
        "EERNO": "E1001", "NAME OF EMPLOYER": "Acme Ghana Ltd",
        "NIA NUMBER": "GHA-001849879-4", "SSNIT SSNO": "C0123456789",
        "FIRST NAME": "Ama", "OTHER NAMES": "Serwaa", "LAST NAME": "Mensah",
        "DOB": "1990-04-12", "GENDER": "F", "NATIONALITY": "Ghanaian",
        "PERMANENT ADDRESS": "12 Independence Ave, Accra",
        "TELEPHONE NUMBER": "0244000001", "EMAIL ADDRESS": "ama@example.com",
        "DATE JOINED SCHEME": "2015-01-01", "NATURE OF EMPLOYMENT": "Permanent",
        "TYPE OF SECTOR": "Private", "MONTHLY SALARY": "6500",
        "CONTRIBUTION STATUS": "Active", "NATURE OF JOB": "Accountant",
    },
    {
        "EERNO": "E1002", "NAME OF EMPLOYER": "Blue Sky Co",
        "NIA NUMBER": "GHA-002233445-1", "SSNIT SSNO": "C0987654321",
        "FIRST NAME": "Kofi", "OTHER NAMES": "", "LAST NAME": "Boateng",
        "DOB": "1985-11-30", "GENDER": "M", "NATIONALITY": "Ghanaian",
        "PERMANENT ADDRESS": "5 Ring Rd, Kumasi",
        "TELEPHONE NUMBER": "0209000002", "EMAIL ADDRESS": "kofi@example.com",
        "DATE JOINED SCHEME": "2012-06-15", "NATURE OF EMPLOYMENT": "Contract",
        "TYPE OF SECTOR": "Private", "MONTHLY SALARY": "8200",
        "CONTRIBUTION STATUS": "Active", "NATURE OF JOB": "Engineer",
    },
    {
        "EERNO": "E1003", "NAME OF EMPLOYER": "Gov Agency",
        "NIA NUMBER": "GHA-003344556-9", "SSNIT SSNO": "C0111222333",
        "FIRST NAME": "Efua", "OTHER NAMES": "Adjoa", "LAST NAME": "Owusu",
        "DOB": "1978-02-05", "GENDER": "F", "NATIONALITY": "Ghanaian",
        "PERMANENT ADDRESS": "88 Cantonments, Accra",
        "TELEPHONE NUMBER": "0271000003", "EMAIL ADDRESS": "efua@example.com",
        "DATE JOINED SCHEME": "2008-09-01", "NATURE OF EMPLOYMENT": "Permanent",
        "TYPE OF SECTOR": "Public", "MONTHLY SALARY": "7100",
        "CONTRIBUTION STATUS": "Dormant", "NATURE OF JOB": "Administrator",
    },
]


def main() -> None:
    out_dir = Path(__file__).resolve().parent.parent / "sample"
    out_dir.mkdir(exist_ok=True)
    out = out_dir / "sample_members.xlsx"

    wb = Workbook()
    ws = wb.active
    ws.title = "members"
    ws.append(CANONICAL_COLUMNS)
    for r in ROWS:
        ws.append([r.get(col, "") for col in CANONICAL_COLUMNS])
    wb.save(out)
    print(f"Wrote {out} with {len(ROWS)} rows.")

    # Also a bulk-lookup list (mix of matching and non-matching, messy formats).
    bulk = out_dir / "sample_bulk_list.csv"
    bulk.write_text(
        "ghana_card\n"
        "GHA-001849879-4\n"
        "gha 002233445 1\n"
        "GHA0033445569\n"
        "GHA-999999999-9\n",   # not in dataset -> NOT FOUND
        encoding="utf-8",
    )
    print(f"Wrote {bulk}.")


if __name__ == "__main__":
    main()
