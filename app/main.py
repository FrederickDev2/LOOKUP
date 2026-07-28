"""FastAPI application: auth, single lookup, bulk lookup, and admin screens.

Server-rendered with Jinja2 templates. No external/CDN assets — all CSS is
served locally. Login (session cookie) is required for every screen except the
login page itself.
"""
from __future__ import annotations

import secrets
from pathlib import Path
from typing import List, Optional

import csv
import io
import json
import re

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from starlette.middleware.sessions import SessionMiddleware

from . import __version__, audit, bulk, users
from .columns import display_fields, export_headers, is_salary
from .memberview import build_member_view, bulk_row
from .config import settings
from .database import init_db
from .ingest import clear_all_members, import_excel, last_import_info
from .lookup import bulk_lookup, single_lookup
from .nia import format_hint, is_valid_nia, normalize_nia

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
# Thousands-separator filter for record counts, e.g. 1234 -> "1,234".
templates.env.filters["comma"] = lambda n: f"{int(n or 0):,}"


def _asset(path: str) -> str:
    """Static URL with a mtime cache-buster so updated CSS/JS always reload."""
    try:
        version = int((BASE_DIR / "static" / path).stat().st_mtime)
    except OSError:
        version = 0
    return f"/static/{path}?v={version}"


templates.env.globals["asset"] = _asset

app = FastAPI(title="UPT NIA Lookup", version=__version__, docs_url=None, redoc_url=None)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="upt_session",
    max_age=settings.session_max_age,
    same_site="strict",
    https_only=settings.cookie_secure,
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.on_event("startup")
def _startup() -> None:
    init_db()
    if settings.secret_key_is_ephemeral:
        print(
            "[WARN] APP_SECRET_KEY is not set — using a random ephemeral key. "
            "Sessions will be invalidated on restart. Set APP_SECRET_KEY in .env."
        )


# --- Security headers (defensive; no external calls) ------------------------

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    # Content-Security-Policy: only same-origin resources; no external hosts.
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' data:; style-src 'self'; "
        "script-src 'self'; form-action 'self'; frame-ancestors 'none'",
    )
    return response


# --- Auth helpers -----------------------------------------------------------

def current_user(request: Request):
    uid = request.session.get("uid")
    if not uid:
        return None
    user = users.get_by_id(uid)
    if not user or not user["is_active"]:
        request.session.clear()
        return None
    return user


def redirect_login() -> RedirectResponse:
    return RedirectResponse("/login", status_code=303)


def render(request: Request, template: str, user, **ctx) -> HTMLResponse:
    context = {
        "request": request,
        "user": user,
        "version": __version__,
        "msg": request.query_params.get("msg"),
        "err": request.query_params.get("err"),
    }
    context.update(ctx)
    return templates.TemplateResponse(template, context)


# --- Root / auth routes -----------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    return RedirectResponse("/search" if current_user(request) else "/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    if current_user(request):
        return RedirectResponse("/search", status_code=303)
    return render(request, "login.html", None)


@app.post("/login", response_class=HTMLResponse)
def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    user = users.authenticate(username, password)
    if not user:
        return render(request, "login.html", None,
                      err="Invalid username or password, or the account is disabled.")
    request.session.clear()
    request.session["uid"] = user["id"]
    request.session["username"] = user["username"]
    request.session["role"] = user["role"]
    return RedirectResponse("/search", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login?msg=You+have+been+logged+out.", status_code=303)


# --- Single lookup ----------------------------------------------------------

def _search_result(request: Request, user, raw: str):
    raw = (raw or "").strip()
    normalized = normalize_nia(raw)

    if not normalized:
        return render(request, "search.html", user, query=raw,
                      hint="Please enter a Ghana Card / NIA number.")

    hint = None if is_valid_nia(normalized) else format_hint()

    # Log the query (normalized value only — never the result).
    audit.log_single_query(user["username"], normalized)

    record = single_lookup(normalized)
    member = build_member_view(record, normalized) if record is not None else None
    return render(
        request, "search.html", user,
        query=raw, normalized=normalized, hint=hint,
        member=member, not_found=record is None,
    )


@app.get("/search", response_class=HTMLResponse)
def search_form(request: Request):
    user = current_user(request)
    if not user:
        return redirect_login()
    # Support deep links like /search?nia=GHA... (e.g. "Open full record").
    q = request.query_params.get("nia")
    if q:
        return _search_result(request, user, q)
    return render(request, "search.html", user)


@app.post("/search", response_class=HTMLResponse)
def search_submit(request: Request, nia: str = Form("")):
    user = current_user(request)
    if not user:
        return redirect_login()
    return _search_result(request, user, nia)


@app.get("/search/export/{nia}")
def search_export(request: Request, nia: str):
    user = current_user(request)
    if not user:
        return redirect_login()
    normalized = normalize_nia(nia)
    record = single_lookup(normalized)
    if record is None:
        return RedirectResponse("/search?err=Record+not+found+for+export.", status_code=303)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Field", "Value"])
    for label, value in display_fields(record):  # salary already excluded
        if (value or "").strip():
            writer.writerow([label, value])
    filename = f"nia_{normalized or 'record'}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- Bulk lookup ------------------------------------------------------------

async def _save_upload(upload: UploadFile, max_bytes: int, allowed_exts) -> Path:
    ext = Path(upload.filename or "").suffix.lower()
    if ext not in allowed_exts:
        raise ValueError(f"Unsupported file type '{ext or '(none)'}'. "
                         f"Allowed: {', '.join(sorted(allowed_exts))}.")
    settings.ensure_dirs()
    token = secrets.token_hex(16)
    dest = settings.tmp_dir / f"{token}{ext}"
    size = 0
    with dest.open("wb") as fh:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > max_bytes:
                fh.close()
                dest.unlink(missing_ok=True)
                raise ValueError(f"File exceeds the maximum allowed size "
                                 f"({max_bytes // (1024 * 1024)} MB).")
            fh.write(chunk)
    return dest


def _build_bulk_exports(token: str, inputs, normalized, records) -> None:
    """Write full-detail CSV/XLSX exports (all fields, salary excluded)."""
    key_union: List[str] = []
    seen = set()
    for rec in records:
        if rec:
            for k in rec.keys():
                if k not in seen and not is_salary(k):
                    seen.add(k)
                    key_union.append(k)
    member_headers = export_headers(key_union)
    headers = ["INPUT NIA", "NORMALIZED NIA", "STATUS"] + member_headers
    rows: List[dict] = []
    for raw, norm, rec in zip(inputs, normalized, records):
        row = {"INPUT NIA": raw, "NORMALIZED NIA": norm,
               "STATUS": "FOUND" if rec else "NOT FOUND"}
        for h in member_headers:
            row[h] = rec.get(h, "") if rec else ""
        rows.append(row)
    bulk.build_exports(token, headers, rows)


@app.get("/bulk", response_class=HTMLResponse)
def bulk_form(request: Request):
    user = current_user(request)
    if not user:
        return redirect_login()
    return render(request, "bulk.html", user, has_results=False)


@app.post("/bulk/run", response_class=HTMLResponse)
async def bulk_run(request: Request, numbers: str = Form(""),
                   listfile: Optional[UploadFile] = File(None)):
    user = current_user(request)
    if not user:
        return redirect_login()

    numbers_raw = numbers or ""
    inputs: List[str] = []

    if listfile is not None and (listfile.filename or "").strip():
        # A file was provided — parse the NIA column from it.
        try:
            dest = await _save_upload(listfile, settings.max_bulk_bytes, bulk.ALLOWED_EXTS)
        except ValueError as exc:
            return render(request, "bulk.html", user, has_results=False,
                          numbers_raw=numbers_raw, err=str(exc))
        try:
            inputs = await run_in_threadpool(
                bulk.extract_nia_from_file, str(dest), dest.suffix.lower())
        except Exception as exc:  # noqa: BLE001
            return render(request, "bulk.html", user, has_results=False,
                          numbers_raw=numbers_raw, err=f"Could not read the file: {exc}")
        finally:
            dest.unlink(missing_ok=True)
        numbers_raw = ""  # results came from a file, keep the paste box clear
    else:
        inputs = [v for v in re.split(r"[\s,;]+", numbers_raw.strip()) if v.strip()]

    if not inputs:
        return render(request, "bulk.html", user, has_results=False, numbers_raw=numbers_raw,
                      err="Paste some Ghana Card numbers or upload a file first.")

    normalized = [normalize_nia(v) for v in inputs]
    records = bulk_lookup(normalized)
    audit.log_bulk_query(user["username"], normalized)

    client_rows = [bulk_row(i, n, r) for i, n, r in zip(inputs, normalized, records)]
    found = sum(1 for r in records if r)
    total = len(inputs)

    token = secrets.token_hex(16)
    await run_in_threadpool(_build_bulk_exports, token, inputs, normalized, records)

    # Embed as JSON for the client renderer; neutralize any "</script>".
    data_json = json.dumps(client_rows, ensure_ascii=False).replace("<", "\\u003c")

    return render(request, "bulk.html", user,
                  has_results=True, numbers_raw=numbers_raw,
                  total=total, found=found, not_found=total - found,
                  token=token, data_json=data_json)


@app.get("/bulk/download/{token}/{fmt}")
def bulk_download(request: Request, token: str, fmt: str):
    user = current_user(request)
    if not user:
        return redirect_login()
    # token is a hex string; reject anything else to avoid path games.
    if not token or not all(c in "0123456789abcdef" for c in token):
        return RedirectResponse("/bulk?err=Invalid+download+token.", status_code=303)
    path = bulk.export_path(token, fmt)
    if not path:
        return RedirectResponse("/bulk?err=Export+not+found+or+expired.", status_code=303)
    media = ("text/csv" if fmt == "csv"
             else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    return FileResponse(str(path), media_type=media, filename=f"nia_bulk_results.{fmt}")


# --- Admin: data import -----------------------------------------------------

def require_admin(request: Request):
    user = current_user(request)
    if not user:
        return None, redirect_login()
    if user["role"] != "admin":
        return None, RedirectResponse("/search?err=Admin+access+required.", status_code=303)
    return user, None


@app.get("/admin", response_class=HTMLResponse)
def admin_home(request: Request):
    user, redir = require_admin(request)
    if redir:
        return redir
    return render(request, "admin.html", user, info=last_import_info())


@app.post("/admin/import", response_class=HTMLResponse)
async def admin_import(request: Request, datafile: UploadFile):
    user, redir = require_admin(request)
    if redir:
        return redir

    filename = datafile.filename or "upload.xlsx"
    if not filename.lower().endswith(".xlsx"):
        return render(request, "admin.html", user, info=last_import_info(),
                      err="Please upload a .xlsx file.")

    try:
        dest = await _save_upload(datafile, settings.max_import_bytes, {".xlsx"})
    except ValueError as exc:
        return render(request, "admin.html", user, info=last_import_info(), err=str(exc))

    try:
        result = await run_in_threadpool(import_excel, str(dest), user["username"])
    except Exception as exc:  # noqa: BLE001
        audit.log_import(filename, 0, 0, user["username"], "failed", str(exc))
        return render(request, "admin.html", user, info=last_import_info(),
                      err=f"Import failed: {exc}")
    finally:
        dest.unlink(missing_ok=True)

    audit.log_import(filename, result.row_count, result.skipped_count,
                     user["username"], "success",
                     f"{result.row_count} rows merged, {result.skipped_count} without a NIA.")
    return RedirectResponse(
        f"/admin?msg=Merged+{result.row_count}+rows+from+{filename}+into+the+dataset.",
        status_code=303,
    )


@app.post("/admin/clear", response_class=HTMLResponse)
def admin_clear(request: Request, confirm: str = Form("")):
    user, redir = require_admin(request)
    if redir:
        return redir
    if (confirm or "").strip() != "CLEAR":
        return RedirectResponse(
            "/admin?err=Type+CLEAR+(in+capitals)+to+confirm+deleting+all+data.",
            status_code=303,
        )
    removed = clear_all_members()
    audit.log_import("(clear all data)", 0, 0, user["username"], "cleared",
                     f"{removed} member records deleted.")
    return RedirectResponse(
        f"/admin?msg=All+data+cleared+({removed}+records+deleted).", status_code=303
    )


# --- Admin: user management -------------------------------------------------

@app.get("/admin/users", response_class=HTMLResponse)
def admin_users(request: Request):
    user, redir = require_admin(request)
    if redir:
        return redir
    return render(request, "users.html", user, all_users=users.list_users())


@app.post("/admin/users/create")
def admin_users_create(request: Request, username: str = Form(...),
                       password: str = Form(...), role: str = Form(...)):
    user, redir = require_admin(request)
    if redir:
        return redir
    try:
        users.create_user(username, password, role, created_by=user["username"])
    except ValueError as exc:
        return RedirectResponse(f"/admin/users?err={exc}", status_code=303)
    return RedirectResponse(f"/admin/users?msg=User+'{username}'+created.", status_code=303)


@app.post("/admin/users/{user_id}/toggle")
def admin_users_toggle(request: Request, user_id: int):
    admin, redir = require_admin(request)
    if redir:
        return redir
    target = users.get_by_id(user_id)
    if not target:
        return RedirectResponse("/admin/users?err=User+not+found.", status_code=303)
    disabling = bool(target["is_active"])
    # Never disable/lock out the last active admin.
    if disabling and target["role"] == "admin" and users.count_active_admins(exclude_id=user_id) == 0:
        return RedirectResponse(
            "/admin/users?err=Cannot+disable+the+last+active+admin.", status_code=303)
    users.set_active(user_id, not disabling)
    state = "disabled" if disabling else "enabled"
    return RedirectResponse(f"/admin/users?msg=User+'{target['username']}'+{state}.", status_code=303)


@app.post("/admin/users/{user_id}/password")
def admin_users_password(request: Request, user_id: int, password: str = Form(...)):
    admin, redir = require_admin(request)
    if redir:
        return redir
    target = users.get_by_id(user_id)
    if not target:
        return RedirectResponse("/admin/users?err=User+not+found.", status_code=303)
    try:
        users.set_password(user_id, password)
    except ValueError as exc:
        return RedirectResponse(f"/admin/users?err={exc}", status_code=303)
    return RedirectResponse(
        f"/admin/users?msg=Password+updated+for+'{target['username']}'.", status_code=303)


# --- Admin: logs ------------------------------------------------------------

@app.get("/admin/logs", response_class=HTMLResponse)
def admin_logs(request: Request):
    user, redir = require_admin(request)
    if redir:
        return redir
    return render(request, "logs.html", user,
                  query_logs=audit.recent_query_logs(300),
                  import_logs=audit.recent_import_logs(100))


@app.get("/healthz")
def healthz():
    return {"status": "ok", "version": __version__}
