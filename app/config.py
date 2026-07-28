"""Application configuration.

All configuration comes from environment variables (optionally loaded from a
local .env file). Nothing sensitive is hardcoded. See .env.example for docs.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv is a convenience; fall back to real env vars.
    def load_dotenv(*_args, **_kwargs):  # type: ignore
        return False

# Project root = the directory that contains this "app" package.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env from the project root if present (no-op if the file is missing).
load_dotenv(BASE_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip())
    except (ValueError, AttributeError):
        return default


def _path(name: str, default: str) -> Path:
    raw = os.environ.get(name, "").strip() or default
    p = Path(raw)
    if not p.is_absolute():
        p = BASE_DIR / p
    return p


class Settings:
    """Resolved runtime settings."""

    def __init__(self) -> None:
        # Session signing key. If unset, generate an ephemeral one and warn:
        # sessions will not survive a restart until APP_SECRET_KEY is set.
        self.secret_key = os.environ.get("APP_SECRET_KEY", "").strip()
        self.secret_key_is_ephemeral = False
        if not self.secret_key or self.secret_key == "change-me-to-a-long-random-string":
            self.secret_key = secrets.token_urlsafe(48)
            self.secret_key_is_ephemeral = True

        # Network binding — defaults to loopback only.
        self.host = os.environ.get("APP_HOST", "127.0.0.1").strip() or "127.0.0.1"
        self.port = _int("APP_PORT", 8000)

        # Storage
        self.db_path = _path("APP_DB_PATH", "./data/upt.db")
        self.tmp_dir = _path("APP_TMP_DIR", "./data/tmp")

        # Session cookie
        self.cookie_secure = _bool("SESSION_COOKIE_SECURE", False)
        self.session_max_age = _int("SESSION_MAX_AGE", 8 * 60 * 60)

        # Upload limits (bytes)
        self.max_import_bytes = _int("MAX_IMPORT_MB", 300) * 1024 * 1024
        self.max_bulk_bytes = _int("MAX_BULK_MB", 25) * 1024 * 1024

        # Seed accounts (only consumed by seed.py)
        self.admin_username = os.environ.get("ADMIN_USERNAME", "admin").strip() or "admin"
        self.admin_password = os.environ.get("ADMIN_PASSWORD", "")
        self.query_username = os.environ.get("QUERY_USERNAME", "query").strip() or "query"
        self.query_password = os.environ.get("QUERY_PASSWORD", "")

    def ensure_dirs(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
