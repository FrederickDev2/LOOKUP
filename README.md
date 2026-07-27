# UPT Member NIA Lookup

A **local, internal-network** web application for United Pension Trustees (UPT) to
look up employee/member records by **Ghana Card (NIA) number**.

It is deliberately self-contained: **no external services, no telemetry, no cloud
calls, no CDN**. Everything runs on your own machine / LAN and works fully offline.

- **Backend:** Python 3 + FastAPI
- **Database:** SQLite (indexed on the normalized NIA number)
- **Parsing:** pandas + openpyxl (streaming import for large files)
- **Frontend:** server-rendered Jinja2 templates + one local CSS file (no build step)
- **Auth:** username + password (bcrypt hashes), two roles (`admin`, `user`)

> ⚠️ **Handles sensitive PII.** Bind it only to a private interface, restrict it to
> the internal LAN at the firewall, and keep exports on authorised machines only.

---

## Table of contents

1. [What it does](#what-it-does)
2. [Quick start (Ubuntu 24.04)](#quick-start-ubuntu-2404)
3. [Configuration (.env)](#configuration-env)
4. [Running as a service (systemd)](#running-as-a-service-systemd)
5. [Firewall — restrict to the internal LAN](#firewall--restrict-to-the-internal-lan)
6. [Local development / trying it out](#local-development--trying-it-out)
7. [Data model & privacy notes](#data-model--privacy-notes)
8. [Project layout](#project-layout)
9. [Troubleshooting](#troubleshooting)

---

## What it does

- **Login required** for every screen. Two roles:
  - `admin` — import data, manage users, view logs, and query.
  - `user` — query only (single + bulk lookup).
- **Single lookup** — type a Ghana Card / NIA number with or without hyphens/spaces
  (`GHA-001849879-4` or `GHA0018498794` both work). Shows all fields **except
  Monthly Salary**, a clear *not found* message, and a format hint for bad input.
- **Bulk lookup** — upload a CSV/Excel list of NIA numbers, pick the column, get a
  results table (one row per input, matched fields or `NOT FOUND`), and export it to
  CSV or Excel.
- **Admin import** — upload the master `.xlsx`; it is parsed and **replaces** the
  SQLite dataset atomically (a failed import keeps the old data). NIA numbers are
  normalized on import (hyphens/whitespace stripped, uppercased) and both the
  original and normalized forms are stored. Shows the last-import timestamp and row
  count; every import is logged.
- **Audit logs (admin only)** — every single/bulk query is logged with the account,
  the **normalized** NIA number(s) searched, and the time. The *result* is never
  stored.

---

## Quick start (Ubuntu 24.04)

Assumes the code lives at `/opt/upt-nia-lookup`. Adjust paths as needed.

### 1. System packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip
```

### 2. Put the code in place & create a service user

```bash
sudo mkdir -p /opt/upt-nia-lookup
# copy this project into /opt/upt-nia-lookup (git clone, scp, rsync, etc.)

# Dedicated, non-login account to run the service:
sudo useradd --system --home /opt/upt-nia-lookup --shell /usr/sbin/nologin upt || true
sudo chown -R upt:upt /opt/upt-nia-lookup
```

### 3. Virtualenv & dependencies

```bash
cd /opt/upt-nia-lookup
sudo -u upt python3 -m venv .venv
sudo -u upt .venv/bin/pip install --upgrade pip
sudo -u upt .venv/bin/pip install -r requirements.txt
```

### 4. Configuration

```bash
sudo -u upt cp .env.example .env
# Generate a strong session key:
.venv/bin/python -c "import secrets; print('APP_SECRET_KEY=' + secrets.token_urlsafe(48))"
# Edit .env: paste APP_SECRET_KEY, set APP_HOST (127.0.0.1 or the private LAN IP),
# APP_PORT, and the seed passwords ADMIN_PASSWORD / QUERY_PASSWORD.
sudo -u upt nano .env
sudo chmod 600 .env
```

### 5. Create the default accounts (first run only)

```bash
sudo -u upt .venv/bin/python seed.py
```

This creates the `admin` account and the shared `query` account using the passwords
from `.env` (or it prompts you if they are blank). It never overwrites an existing
account.

### 6. Start it

```bash
sudo -u upt .venv/bin/python run.py
# or directly:
# sudo -u upt .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open `http://<APP_HOST>:<APP_PORT>/` from a machine on the internal LAN and sign in.

For a persistent install, use the **systemd** service below instead of running by
hand.

---

## Configuration (.env)

All settings are environment variables (loaded from `.env`). See `.env.example` for
the annotated list. Key ones:

| Variable | Purpose | Default |
| --- | --- | --- |
| `APP_SECRET_KEY` | Signs the login session cookie. **Set a long random value.** | *(ephemeral if unset — sessions drop on restart)* |
| `APP_HOST` | Local/private interface to bind. `127.0.0.1` = this machine only; or a private LAN IP. **Never `0.0.0.0`.** | `127.0.0.1` |
| `APP_PORT` | Port to listen on. | `8000` |
| `APP_DB_PATH` | SQLite database file. | `./data/upt.db` |
| `APP_TMP_DIR` | Scratch dir for upload/export temp files. | `./data/tmp` |
| `SESSION_COOKIE_SECURE` | `true` only if served over HTTPS. | `false` |
| `SESSION_MAX_AGE` | Session lifetime (seconds). | `28800` (8h) |
| `MAX_IMPORT_MB` | Max import file size (MB). | `300` |
| `MAX_BULK_MB` | Max bulk-list file size (MB). | `25` |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | Seed admin (used by `seed.py`). | `admin` / *(prompted)* |
| `QUERY_USERNAME` / `QUERY_PASSWORD` | Seed shared query account. | `query` / *(prompted)* |

`run.py` **refuses to start** if `APP_HOST` is `0.0.0.0` / `::`, so PII is never
accidentally served on all interfaces.

---

## Running as a service (systemd)

A unit file is provided at `deploy/upt-nia-lookup.service`.

```bash
sudo cp deploy/upt-nia-lookup.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now upt-nia-lookup

# check it
systemctl status upt-nia-lookup
journalctl -u upt-nia-lookup -f
```

The unit reads `APP_HOST`/`APP_PORT` from `.env` (via `EnvironmentFile`) and runs
`run.py`, so binding stays under your control and cannot become `0.0.0.0`. It also
applies basic hardening (`NoNewPrivileges`, `ProtectSystem=strict`, a writable path
limited to `data/`).

To update after changing code:

```bash
sudo systemctl restart upt-nia-lookup
```

---

## Firewall — restrict to the internal LAN

Binding to `127.0.0.1` already limits access to the host itself. If you bind to a
private LAN IP so other internal machines can reach it, **also** restrict it at the
firewall so only the internal subnet can connect. Example with `ufw` (adjust the
subnet and port):

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow the app port ONLY from the internal subnet (example: 10.0.0.0/24):
sudo ufw allow from 10.0.0.0/24 to any port 8000 proto tcp

# (Optional) keep SSH from the same subnet:
sudo ufw allow from 10.0.0.0/24 to any port 22 proto tcp

sudo ufw enable
sudo ufw status verbose
```

Do **not** open the port to `Anywhere`. This app must never be reachable from the
public internet. There are no outbound calls, so `allow outgoing` is only for OS
updates, etc.

---

## Local development / trying it out

You need Python 3.10+ (3.11/3.12 recommended). On Windows/macOS/Linux:

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # then set APP_SECRET_KEY + seed passwords
python seed.py                # create admin + query accounts
python scripts/make_sample_data.py   # optional: fake sample .xlsx + bulk CSV
python run.py                 # http://127.0.0.1:8000
```

Then: sign in as `admin` → **Import data** → upload `sample/sample_members.xlsx` →
**Single lookup** try `GHA-001849879-4` → **Bulk lookup** upload
`sample/sample_bulk_list.csv`.

Run the tests:

```bash
pip install pytest
python -m pytest
```

---

## Data model & privacy notes

- **NIA normalization** (import *and* lookup): strip all hyphens + whitespace, then
  uppercase → `GHA-001849879-4` becomes `GHA0018498794`. Both original and normalized
  forms are stored; the normalized column is indexed (`idx_members_nia`).
- **Monthly Salary** is stored but **never** returned to any screen or export.
- **Query logs** store only *who / what-normalized-NIA / when* — never whether a
  record was found or any record content.
- The raw Excel is **not** kept in memory for querying — it is imported once into
  SQLite and all lookups hit the DB. Upload temp files live under `APP_TMP_DIR`.
- No external network calls, analytics, fonts, or CDN assets. A restrictive
  `Content-Security-Policy` (`default-src 'self'`) is sent on every response.

---

## Project layout

```
UPT_NIA_APP/
├─ app/
│  ├─ main.py           # FastAPI app + all routes
│  ├─ config.py         # env-based settings
│  ├─ database.py       # SQLite schema + connections
│  ├─ nia.py            # NIA normalize/validate
│  ├─ columns.py        # canonical columns + salary exclusion
│  ├─ security.py       # bcrypt hashing
│  ├─ users.py          # account CRUD / auth
│  ├─ audit.py          # query + import logging
│  ├─ ingest.py         # streaming .xlsx import → SQLite
│  ├─ lookup.py         # single + bulk lookup
│  ├─ bulk.py           # bulk file parse/preview/export
│  ├─ templates/        # Jinja2 templates
│  └─ static/style.css  # single local stylesheet
├─ deploy/upt-nia-lookup.service   # systemd unit
├─ scripts/make_sample_data.py     # fake test data generator
├─ tests/test_nia.py
├─ seed.py              # first-run account seeding
├─ run.py               # launcher (enforces no 0.0.0.0)
├─ requirements.txt
├─ .env.example
├─ README.md
└─ ADMIN_GUIDE.md
```

---

## Troubleshooting

- **"REFUSING TO START … 0.0.0.0"** — set `APP_HOST` to `127.0.0.1` or a specific
  private LAN IP in `.env`.
- **Logged out after every restart** — `APP_SECRET_KEY` is not set; set it in `.env`.
- **Import says "Could not find a 'NIA NUMBER' column"** — the header row must contain
  a column named `NIA NUMBER` (case/spacing-insensitive). Check the sheet.
- **Import is slow / memory** — imports stream row-by-row and insert in batches, so
  memory stays low even for 150–200 MB files; a large file can still take a couple of
  minutes. Wait for the page to finish.
- **Can't reach it from another machine** — you bound to `127.0.0.1` (host-only). Bind
  to the private LAN IP and open the firewall for the internal subnet only.
