"""Cuentas asignadas (multicuenta), vistas por persona: qué cuentas abre cada quien en su webmail.

Misma tabla que «Buzones compartidos» (`mail_delegation`: mailbox = la cuenta asignada,
delegate = la persona). El administrador general asigna cualquier cuenta de cualquier dominio
a cualquier persona. El webmail comprueba la asignación en cada petición: quitarla corta el
acceso al instante. `completo` = leer, enviar como esa cuenta y gestionarla; si no, solo lectura.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import require_role
from app.shared.router import _doveadm_acl_delete, _doveadm_acl_set

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/asignaciones", tags=["asignaciones"])

# Permisos IMAP (ACL de Dovecot) para que un cliente de escritorio (Thunderbird, Outlook) vea
# la cuenta como carpeta compartida. El webmail no los necesita (usa la credencial maestra),
# pero así una sola pantalla deja todo coherente. Si una carpeta no existe, se sigue con las demás.
_CARPETAS = ("INBOX", "Sent", "Drafts", "Trash", "Junk")
_COMPLETO = ["lookup", "read", "write", "write-seen", "write-deleted", "insert", "expunge", "create", "delete"]
_LECTURA = ["lookup", "read"]


async def _acl_sincronizar(cuenta: str, persona: str, completo: bool | None) -> None:
    """completo=None quita el permiso; True/False lo pone completo o de solo lectura."""
    objetivo = f"user={persona}"
    for carpeta in _CARPETAS:
        try:
            if completo is None:
                await asyncio.to_thread(_doveadm_acl_delete, cuenta, carpeta, objetivo)
            else:
                await asyncio.to_thread(_doveadm_acl_set, cuenta, carpeta, objetivo, _COMPLETO if completo else _LECTURA)
        except Exception as exc:  # carpeta inexistente u otro detalle: no impide la asignación
            log.info("acl %s %s/%s -> %s: %s", "quitar" if completo is None else "poner", cuenta, carpeta, persona, exc)

_SELECT = """SELECT d.id, lower(d.mailbox) AS cuenta, lower(d.delegate) AS persona,
                    COALESCE(d.can_send_as, false) AS completo, d.created_at,
                    mc.name AS nombre_cuenta, mp.name AS nombre_persona
               FROM mail_delegation d
               LEFT JOIN mailbox mc ON mc.username = lower(d.mailbox)
               LEFT JOIN mailbox mp ON mp.username = lower(d.delegate)"""


def _direccion(valor, que: str) -> str:
    direccion = str(valor or "").strip().lower()
    if direccion.count("@") != 1 or " " in direccion or "\n" in direccion or not direccion.split("@")[0]:
        raise HTTPException(400, f"{que}: escribe una dirección con la forma usuario@dominio")
    return direccion


def _fila(f) -> dict:
    datos = dict(f)
    datos["created_at"] = f["created_at"].isoformat() if f["created_at"] else None
    return datos


async def _auditar(request: Request, admin: dict, accion: str, cuenta: str, detalles: dict):
    await request.app.state.db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        admin["id"], admin["username"], accion, cuenta, json.dumps(detalles), request.headers.get("x-real-ip", "unknown"))


async def _por_id(request: Request, id_: int):
    fila = await request.app.state.db.fetchrow(_SELECT + " WHERE d.id = $1", id_)
    if not fila:
        raise HTTPException(404, "Esa asignación ya no existe")
    return fila


@router.get("")
async def listar(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    filas = await request.app.state.db.fetch(_SELECT + " ORDER BY persona, cuenta")
    return [_fila(f) for f in filas]


@router.post("", status_code=201)
async def asignar(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    datos = await request.json()
    persona, cuenta = _direccion(datos.get("persona"), "Persona"), _direccion(datos.get("cuenta"), "Cuenta")
    completo = bool(datos.get("completo", True))
    if persona == cuenta:
        raise HTTPException(400, "Una persona no necesita que le asignen su propia cuenta")
    db = request.app.state.db
    activas = {f["username"] for f in await db.fetch(
        "SELECT username FROM mailbox WHERE username = ANY($1::varchar[]) AND active = true", [cuenta, persona])}
    if cuenta not in activas:
        raise HTTPException(400, f"La cuenta {cuenta} no existe o está desactivada")
    if persona not in activas:
        raise HTTPException(400, f"La persona {persona} no tiene una cuenta activa")
    # El webmail nunca abre la cuenta de un administrador general: no se deja asignarla.
    if await db.fetchval("SELECT 1 FROM admin WHERE lower(username) = $1 AND superadmin = true", cuenta):
        raise HTTPException(400, "La cuenta de un administrador general no se puede asignar")
    antes = await db.fetchrow(
        "SELECT id, COALESCE(can_send_as, false) AS completo FROM mail_delegation WHERE lower(mailbox) = $1 AND lower(delegate) = $2",
        cuenta, persona)
    if antes:
        await db.execute("UPDATE mail_delegation SET can_send_as = $2 WHERE id = $1", antes["id"], completo)
        id_ = antes["id"]
    else:
        id_ = await db.fetchval(
            "INSERT INTO mail_delegation (mailbox, delegate, can_send_as) VALUES ($1, $2, $3) RETURNING id",
            cuenta, persona, completo)
    await _acl_sincronizar(cuenta, persona, completo)
    await _auditar(request, admin, "asignacion_guardar", cuenta,
                   {"persona": persona, "completo": completo, "antes": antes["completo"] if antes else None})
    return _fila(await _por_id(request, id_))


@router.put("/{id_}")
async def cambiar_permiso(id_: int, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    fila = await _por_id(request, id_)
    completo = bool((await request.json()).get("completo", True))
    await request.app.state.db.execute("UPDATE mail_delegation SET can_send_as = $2 WHERE id = $1", id_, completo)
    await _acl_sincronizar(fila["cuenta"], fila["persona"], completo)
    await _auditar(request, admin, "asignacion_permiso", fila["cuenta"],
                   {"persona": fila["persona"], "completo": completo, "antes": fila["completo"]})
    return _fila(await _por_id(request, id_))


@router.delete("/{id_}")
async def quitar(id_: int, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    fila = await _por_id(request, id_)
    await request.app.state.db.execute("DELETE FROM mail_delegation WHERE id = $1", id_)
    await _acl_sincronizar(fila["cuenta"], fila["persona"], None)
    await _auditar(request, admin, "asignacion_quitar", fila["cuenta"], {"persona": fila["persona"], "completo": fila["completo"]})
    return {"ok": True}
