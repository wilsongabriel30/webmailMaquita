import asyncio
import json
from asyncio.subprocess import PIPE
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException, Depends
from app.auth.dependencies import get_current_admin, require_role

router = APIRouter(prefix="/api/autoresponder", tags=["autoresponder"])

import re as _re

_USER_RE = _re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9.-]+$")
_FECHA_RE = _re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _partes_usuario(username: str):
    """Valida el buzón y devuelve (local, domain) seguros para construir rutas.
    Rechaza cualquier cosa que permita traversal o inyección de shell/Sieve."""
    u = (username or "").strip()
    if not _USER_RE.match(u):
        raise HTTPException(400, "buzón inválido")
    local, domain = u.split("@", 1)
    for parte in (local, domain):
        if parte in (".", "..") or "/" in parte or ".." in parte:
            raise HTTPException(400, "buzón inválido")
    return local, domain


def _sieve_str(valor: str, una_linea: bool = False) -> str:
    """Escapa un valor para insertarlo en una cadena Sieve entre comillas dobles."""
    v = str(valor or "")
    if una_linea:
        v = v.replace("\r", " ").replace("\n", " ")
    return v.replace("\\", "\\\\").replace('"', '\\"')


def _db(r: Request):
    return r.app.state.db


async def _audit(r, a, action, target=None, details=None):
    await _db(r).execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        a["id"], a["username"], action, target, json.dumps(details) if details else None,
        r.headers.get("X-Real-IP", r.client.host if r.client else ""))


async def _ensure_tables(db):
    await db.execute("""
        CREATE TABLE IF NOT EXISTS mail_autoresponders (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            active BOOLEAN DEFAULT false,
            subject VARCHAR(500) NOT NULL DEFAULT 'Fuera de oficina',
            body TEXT NOT NULL DEFAULT '',
            start_date DATE,
            end_date DATE,
            reply_once_per_day BOOLEAN DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            modified_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)


async def _run(*cmd) -> tuple[str, str, int]:
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
    out, err = await proc.communicate()
    return out.decode(errors="replace"), err.decode(errors="replace"), proc.returncode


def _generate_sieve(ar: dict) -> str:
    """Generar script Sieve para vacation, con valores escapados (evita inyección)."""
    subject = _sieve_str(ar.get("subject", "Fuera de oficina"), una_linea=True)
    body = _sieve_str(ar.get("body", ""))
    days = "1" if ar.get("reply_once_per_day", True) else "0"

    lines = ['require ["vacation"];', ""]

    inicio, fin = ar.get("start_date"), ar.get("end_date")
    if inicio and fin:
        if not (_FECHA_RE.match(str(inicio)) and _FECHA_RE.match(str(fin))):
            raise HTTPException(400, "fechas inválidas (AAAA-MM-DD)")
        lines.append('require ["date", "relational"];')
        lines.append(f'if allof(currentdate :value "ge" "date" "{inicio}",')
        lines.append(f'         currentdate :value "le" "date" "{fin}") {{')
        lines.append(f'  vacation :days {days} :subject "{subject}"')
        lines.append(f'    "{body}";')
        lines.append("}")
    else:
        lines.append(f'vacation :days {days} :subject "{subject}"')
        lines.append(f'  "{body}";')

    return "\n".join(lines)


@router.get("")
async def list_autoresponders(request: Request, admin: dict = Depends(get_current_admin)):
    db = _db(request)
    await _ensure_tables(db)
    rows = await db.fetch("""
        SELECT ar.*, m.name as user_fullname
        FROM mail_autoresponders ar
        LEFT JOIN mailbox m ON ar.username = m.username
        ORDER BY ar.username
    """)
    return [dict(r) for r in rows]


@router.get("/{username:path}")
async def get_autoresponder(username: str, request: Request, admin: dict = Depends(get_current_admin)):
    db = _db(request)
    await _ensure_tables(db)
    row = await db.fetchrow("SELECT * FROM mail_autoresponders WHERE username = $1", username)
    if not row:
        return {"username": username, "active": False, "subject": "Fuera de oficina", "body": ""}
    return dict(row)


@router.post("")
async def set_autoresponder(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    data = await request.json()
    username = data.get("username", "").strip()
    if not username or "@" not in username:
        raise HTTPException(400, "username@domain requerido")

    db = _db(request)
    await _ensure_tables(db)

    row = await db.fetchrow("""
        INSERT INTO mail_autoresponders (username, active, subject, body, start_date, end_date, reply_once_per_day)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        ON CONFLICT (username) DO UPDATE SET
            active=$2, subject=$3, body=$4, start_date=$5, end_date=$6, reply_once_per_day=$7, modified_at=NOW()
        RETURNING *
    """, username,
        data.get("active", False),
        data.get("subject", "Fuera de oficina"),
        data.get("body", ""),
        data.get("start_date"),
        data.get("end_date"),
        data.get("reply_once_per_day", True))

    # Deploy sieve script if active
    local, domain = _partes_usuario(username)
    base = f"/var/vmail/{domain}/{local}"
    if data.get("active"):
        sieve = _generate_sieve(data)
        sieve_dir = f"{base}/sieve"

        await _run("mkdir", "-p", sieve_dir)
        sieve_path = f"{sieve_dir}/vacation.sieve"

        # Escribir el script Sieve desde Python (sin shell ni heredoc)
        import os as _os
        with open(sieve_path, "w", encoding="utf-8") as fh:
            fh.write(sieve)

        # Compile
        await _run("sievec", sieve_path)

        # Activate: symlink .dovecot.sieve
        active_link = f"{base}/.dovecot.sieve"
        await _run("ln", "-sf", sieve_path, active_link)

        # Fix permissions
        await _run("chown", "-R", "vmail:vmail", sieve_dir)
        await _run("chown", "vmail:vmail", active_link)
    else:
        # Deactivate
        active_link = f"{base}/.dovecot.sieve"
        await _run("rm", "-f", active_link)

    await _audit(request, admin, "autoresponder_set", username, {"active": data.get("active")})
    return dict(row)


@router.delete("/{username:path}")
async def delete_autoresponder(username: str, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    local, domain = _partes_usuario(username)
    db = _db(request)
    await db.execute("DELETE FROM mail_autoresponders WHERE username = $1", username)

    # Remove sieve
    base = f"/var/vmail/{domain}/{local}"
    await _run("rm", "-f", f"{base}/.dovecot.sieve")
    await _run("rm", "-rf", f"{base}/sieve")

    await _audit(request, admin, "autoresponder_delete", username)
    return {"ok": True}
