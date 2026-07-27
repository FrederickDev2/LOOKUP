#!/usr/bin/env python3
"""First-run seed script.

Creates the two default accounts:
  * an admin account   (role: admin)  — import data, manage users, view logs
  * a shared query acct (role: user)  — query only

Passwords are taken from environment variables (ADMIN_PASSWORD / QUERY_PASSWORD,
typically set in .env) or, if not provided, prompted for interactively. They are
NEVER hardcoded and are stored only as bcrypt hashes.

Existing accounts are left untouched (this script never overwrites a password).

Usage:
    python seed.py
"""
from __future__ import annotations

import getpass
import sys

from app.config import settings
from app.database import init_db
from app import users


def _resolve_password(env_value: str, who: str) -> str:
    if env_value:
        return env_value
    if not sys.stdin.isatty():
        print(f"ERROR: No password provided for '{who}'. Set it in .env "
              f"(e.g. ADMIN_PASSWORD=...) or run this script interactively.",
              file=sys.stderr)
        sys.exit(1)
    while True:
        p1 = getpass.getpass(f"Set password for '{who}': ")
        if len(p1) < 8:
            print("  Password must be at least 8 characters. Try again.")
            continue
        p2 = getpass.getpass(f"Confirm password for '{who}': ")
        if p1 != p2:
            print("  Passwords did not match. Try again.")
            continue
        return p1


def main() -> None:
    init_db()
    print(f"Database ready at: {settings.db_path}")

    admin_pw = _resolve_password(settings.admin_password, settings.admin_username)
    admin_status = users.upsert_seed_user(settings.admin_username, admin_pw, "admin")
    print(f"  admin account '{settings.admin_username}': {admin_status}")

    query_pw = _resolve_password(settings.query_password, settings.query_username)
    query_status = users.upsert_seed_user(settings.query_username, query_pw, "user")
    print(f"  query account '{settings.query_username}': {query_status}")

    print("Seeding complete.")


if __name__ == "__main__":
    main()
