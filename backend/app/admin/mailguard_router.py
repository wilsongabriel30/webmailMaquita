"""
Bloqueos de correo (remitentes y extensiones prohibidas) — Rspamd multimap.
Administra los mapas /etc/rspamd/local.d/maps/banned_*.map desde el panel.
Rspamd recarga los mapas automaticamente al detectar el cambio de archivo.
Prefix: /api/admin/mailguard
"""

import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.admin import audit_service
from app.auth.dependencies import require_admin

router = APIRouter(prefix="/api/admin/mailguard", tags=["admin-mailguard"])

MAP_DOMAINS = "/etc/rspamd/local.d/maps/banned_sender_domains.map"
MAP_SENDERS = "/etc/rspamd/local.d/maps/banned_senders.map"
MAP_EXTENSIONS = "/etc/rspamd/local.d/maps/banned_extensions.map"

DOMAIN_RE = re.compile(
    r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$"
)
EMAIL_RE = re.compile(r"^[a-z0-9._%+=-]+@[a-z0-9.-]+\.[a-z]{2,}$")
EXT_RE = re.compile(r"^[a-z0-9]{1,10}$")
EXT_LINE_RE = re.compile(r"^/\\\.([a-z0-9]{1,10})\$/i$")


def _get_ip(request: Request) -> str:
    return request.headers.get(
        "X-Real-IP", request.client.host if request.client else "unknown"
    )


async def _audit(
    request: Request, admin: str, action: str, target: str = None, details: dict = None
):
    db = request.app.state.db_pool
    await audit_service.log_action(db, admin, action, target, details, _get_ip(request))


def _read(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def _write(path: str, content: str):
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except PermissionError:
        raise HTTPException(500, f"Sin permisos para escribir {path}")


def _parse_entries(content: str, value_transform=None) -> list[dict]:
    """Lineas de valor precedidas opcionalmente por comentario `# razon - fecha`."""
    entries = []
    pending = ""
    for line in content.splitlines():
        s = line.strip()
        if not s:
            pending = ""
            continue
        if s.startswith("#"):
            pending = s.lstrip("# ").strip()
            continue
        value = value_transform(s) if value_transform else s
        if value is None:
            pending = ""
            continue
        parts = pending.rsplit(" - ", 1) if pending else ["", ""]
        entries.append(
            {
                "value": value,
                "reason": parts[0] if parts else "",
                "date": parts[1] if len(parts) >= 2 else "",
            }
        )
        pending = ""
    return entries


def _ext_from_line(line: str):
    m = EXT_LINE_RE.match(line)
    return m.group(1) if m else None


def _append_entry(path: str, raw_line: str, reason: str):
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    content = _read(path)
    if content and not content.endswith("\n"):
        content += "\n"
    content += f"\n# {reason} - {date_str}\n{raw_line}\n"
    _write(path, content)


def _remove_entry(path: str, match_fn) -> bool:
    content = _read(path)
    lines = content.splitlines()
    new_lines: list[str] = []
    found = False
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and match_fn(s):
            found = True
            if (
                new_lines
                and new_lines[-1].strip().startswith("#")
                and " - " in new_lines[-1]
            ):
                new_lines.pop()
            continue
        new_lines.append(line)
    if found:
        _write(path, "\n".join(new_lines) + "\n")
    return found


class SenderAddRequest(BaseModel):
    value: str
    reason: str = ""


class ExtensionAddRequest(BaseModel):
    ext: str
    reason: str = ""


@router.get("/summary")
async def summary(request: Request, admin: str = Depends(require_admin)):
    domains = _parse_entries(_read(MAP_DOMAINS))
    senders = _parse_entries(_read(MAP_SENDERS))
    exts = _parse_entries(_read(MAP_EXTENSIONS), _ext_from_line)
    return {
        "domains": len(domains),
        "senders": len(senders),
        "extensions": len(exts),
    }


@router.get("/senders")
async def list_senders(request: Request, admin: str = Depends(require_admin)):
    return {
        "domains": _parse_entries(_read(MAP_DOMAINS)),
        "addresses": _parse_entries(_read(MAP_SENDERS)),
    }


@router.post("/senders")
async def add_sender(
    body: SenderAddRequest, request: Request, admin: str = Depends(require_admin)
):
    value = body.value.strip().lower()
    reason = body.reason.strip() or "Bloqueado desde el panel"
    if "@" in value:
        if not EMAIL_RE.match(value):
            raise HTTPException(400, f"Direccion invalida: {value}")
        path = MAP_SENDERS
        kind = "direccion"
    else:
        if not DOMAIN_RE.match(value):
            raise HTTPException(400, f"Dominio invalido: {value}")
        path = MAP_DOMAINS
        kind = "dominio"
    existing = {e["value"].lower() for e in _parse_entries(_read(path))}
    if value in existing:
        raise HTTPException(409, f"{value} ya esta bloqueado")
    _append_entry(path, value, reason)
    await _audit(
        request, admin, "mailguard_sender_add", value, {"reason": reason, "tipo": kind}
    )
    return {
        "ok": True,
        "message": f"Bloqueado {kind}: {value}. Los proximos correos se rechazaran.",
    }


@router.delete("/senders/{value:path}")
async def remove_sender(
    value: str, request: Request, admin: str = Depends(require_admin)
):
    value = value.strip().lower()
    path = MAP_SENDERS if "@" in value else MAP_DOMAINS
    if not _remove_entry(path, lambda s: s.lower() == value):
        raise HTTPException(404, f"{value} no esta en la lista")
    await _audit(request, admin, "mailguard_sender_remove", value)
    return {"ok": True, "message": f"Desbloqueado: {value}"}


@router.get("/extensions")
async def list_extensions(request: Request, admin: str = Depends(require_admin)):
    return {"extensions": _parse_entries(_read(MAP_EXTENSIONS), _ext_from_line)}


@router.post("/extensions")
async def add_extension(
    body: ExtensionAddRequest, request: Request, admin: str = Depends(require_admin)
):
    ext = body.ext.strip().lower().lstrip(".")
    reason = body.reason.strip() or "Bloqueada desde el panel"
    if not EXT_RE.match(ext):
        raise HTTPException(
            400, f"Extension invalida: {ext} (solo letras/numeros, max 10)"
        )
    if ext in {
        "pdf",
        "doc",
        "docx",
        "xls",
        "xlsx",
        "ppt",
        "pptx",
        "jpg",
        "jpeg",
        "png",
        "txt",
        "csv",
        "zip",
    }:
        raise HTTPException(
            400, f"No se permite bloquear .{ext} (extension de uso comun)"
        )
    existing = {
        e["value"] for e in _parse_entries(_read(MAP_EXTENSIONS), _ext_from_line)
    }
    if ext in existing:
        raise HTTPException(409, f".{ext} ya esta bloqueada")
    _append_entry(MAP_EXTENSIONS, f"/\\.{ext}$/i", reason)
    await _audit(request, admin, "mailguard_extension_add", ext, {"reason": reason})
    return {
        "ok": True,
        "message": f"Extension .{ext} bloqueada. Adjuntos .{ext} se rechazaran.",
    }


@router.delete("/extensions/{ext}")
async def remove_extension(
    ext: str, request: Request, admin: str = Depends(require_admin)
):
    ext = ext.strip().lower().lstrip(".")
    if not _remove_entry(MAP_EXTENSIONS, lambda s: _ext_from_line(s) == ext):
        raise HTTPException(404, f".{ext} no esta en la lista")
    await _audit(request, admin, "mailguard_extension_remove", ext)
    return {"ok": True, "message": f"Extension .{ext} desbloqueada"}
