#!/usr/bin/env python3
"""Convenience launcher.

Reads host/port from configuration (.env) and starts uvicorn bound to the
configured local interface. Refuses to bind to 0.0.0.0 to avoid accidentally
exposing sensitive PII on all interfaces — set APP_HOST to a specific private
LAN IP (or leave it as 127.0.0.1) instead.

You can also run the server directly:
    uvicorn app.main:app --host 127.0.0.1 --port 8000
"""
from __future__ import annotations

import sys

import uvicorn

from app.config import settings


def main() -> None:
    if settings.host in {"0.0.0.0", "::", ""}:
        print(
            "REFUSING TO START: APP_HOST is set to an all-interfaces address "
            f"('{settings.host}'). This app handles sensitive PII and must bind "
            "to a specific local/private interface. Set APP_HOST to 127.0.0.1 or "
            "the server's private LAN IP in .env.",
            file=sys.stderr,
        )
        sys.exit(2)

    print(f"Starting UPT NIA Lookup on http://{settings.host}:{settings.port}")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        log_level="info",
        proxy_headers=False,
    )


if __name__ == "__main__":
    main()
