"""Administradores de dominio: quién entra al portal de dominio y qué dominios gestiona.

Solo el superadministrador. El portal de dominio es otro servicio (otro puerto, otro usuario
de base de datos) y NO puede crear administradores ni asignarse dominios: eso se decide aquí.
Las cuentas del portal viven en pd_admins, aparte de admin_users: una cuenta de dominio no
sirve para entrar a este panel.
"""

import json
import re

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import require_superadmin

router = APIRouter(prefix="/api/admins-dominio", tags=["admins-dominio"])

_USUARIO = re.compile(r"^[a-z0-9][a-z0-9._@-]{2,254}$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
CLAVE_MINIMA = 10


def _db(r: Request):
    return r.app.state.db


def _hash(clave: str) -> str:
    return bcrypt.hashpw(clave.encode(), bcrypt.gensalt(rounds=12)).decode()


def _clave_valida(clave) -> str:
    clave = str(clave or "")
    if not CLAVE_MINIMA <= len(clave) <= 128:
        raise HTTPException(400, f"La contraseña debe tener entre {CLAVE_MINIMA} y 128 caracteres")
    clases = sum(bool(re.search(p, clave)) for p in (r"[a-z]", r"[A-Z]", r"\d", r"[^A-Za-z0-9]"))
    if clases < 3:
        raise HTTPException(400, "La contraseña debe combinar al menos tres de: minúsculas, mayúsculas, números y símbolos")
    return clave


async def _dominios_validos(db, pedidos) -> list[str]:
    pedidos = sorted({str(d).strip().lower() for d in (pedidos or []) if str(d).strip()})
    existentes = {f["domain"] for f in await db.fetch("SELECT domain FROM domain WHERE domain = ANY($1::varchar[])", pedidos)}
    faltan = [d for d in pedidos if d not in existentes]
    if faltan:
        raise HTTPException(400, "Dominio inexistente: " + ", ".join(faltan))
    return pedidos


async def _asignar(con, admin_id: int, dominios: list[str], quien: str):
    await con.execute("DELETE FROM pd_admin_dominios WHERE admin_id = $1", admin_id)
    for d in dominios:
        await con.execute(
            "INSERT INTO pd_admin_dominios (admin_id, domain, assigned_by) VALUES ($1,$2,$3)", admin_id, d, quien)


async def _audit(r: Request, a: dict, accion: str, objetivo: str, detalles: dict | None = None):
    await _db(r).execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        a["id"], a["username"], accion, objetivo, json.dumps(detalles) if detalles else None,
        r.headers.get("X-Real-IP", r.client.host if r.client else ""),
    )


@router.get("")
async def listar(request: Request, admin: dict = Depends(require_superadmin)):
    filas = await _db(request).fetch(
        """SELECT a.id, a.username, a.display_name, a.active, a.must_change_password, a.last_login,
                  a.locked_until, a.created_by, a.created_at,
                  COALESCE(array_agg(d.domain ORDER BY d.domain) FILTER (WHERE d.domain IS NOT NULL), '{}') AS dominios
             FROM pd_admins a LEFT JOIN pd_admin_dominios d ON d.admin_id = a.id
            GROUP BY a.id ORDER BY a.username"""
    )
    return [dict(f) for f in filas]


@router.get("/auditoria")
async def auditoria(request: Request, limite: int = 200, admin: dict = Depends(require_superadmin)):
    filas = await _db(request).fetch(
        "SELECT admin_username, action, target, details, ip, created_at FROM pd_auditoria ORDER BY created_at DESC LIMIT $1",
        max(1, min(limite, 1000)),
    )
    return [{**dict(f), "details": json.loads(f["details"]) if f["details"] else None} for f in filas]


@router.post("", status_code=201)
async def crear(request: Request, admin: dict = Depends(require_superadmin)):
    datos = await request.json()
    usuario = str(datos.get("username", "")).strip().lower()
    if not _USUARIO.match(usuario):
        raise HTTPException(400, "Usuario inválido: de 3 a 255 caracteres, letras, números, punto, guion o arroba")
    clave = _clave_valida(datos.get("password"))
    db = _db(request)
    dominios = await _dominios_validos(db, datos.get("dominios"))
    if not dominios:
        raise HTTPException(400, "Asigna al menos un dominio")
    nombre = _CONTROL.sub(" ", str(datos.get("display_name", ""))).strip()[:255]
    try:
        async with db.acquire() as con, con.transaction():
            nuevo = await con.fetchval(
                "INSERT INTO pd_admins (username, password_hash, display_name, created_by) VALUES ($1,$2,$3,$4) RETURNING id",
                usuario, _hash(clave), nombre, admin["username"],
            )
            await _asignar(con, nuevo, dominios, admin["username"])
    except Exception as e:
        if "duplicate key" in str(e):
            raise HTTPException(409, "Ese usuario ya existe")
        raise
    await _audit(request, admin, "admin_dominio_crear", usuario, {"dominios": dominios})
    return {"id": nuevo, "username": usuario, "dominios": dominios}


@router.put("/{admin_id}")
async def editar(admin_id: int, request: Request, admin: dict = Depends(require_superadmin)):
    datos = await request.json()
    db = _db(request)
    actual = await db.fetchrow("SELECT * FROM pd_admins WHERE id = $1", admin_id)
    if not actual:
        raise HTTPException(404, "No encontrado")
    nueva_clave = _hash(_clave_valida(datos["password"])) if datos.get("password") else None
    dominios = await _dominios_validos(db, datos["dominios"]) if "dominios" in datos else None
    activa = bool(datos["active"]) if "active" in datos else actual["active"]
    nombre = _CONTROL.sub(" ", str(datos["display_name"])).strip()[:255] if "display_name" in datos else actual["display_name"]
    async with db.acquire() as con, con.transaction():
        await con.execute(
            """UPDATE pd_admins SET display_name = $2, active = $3,
                      password_hash = COALESCE($4, password_hash),
                      must_change_password = CASE WHEN $4::text IS NULL THEN must_change_password ELSE true END,
                      failed_attempts = 0, locked_until = NULL
                WHERE id = $1""",
            admin_id, nombre, activa, nueva_clave,
        )
        if dominios is not None:
            await _asignar(con, admin_id, dominios, admin["username"])
        # Clave nueva o cuenta desactivada: sus sesiones abiertas dejan de valer al instante.
        if nueva_clave or not activa:
            await con.execute(
                "UPDATE pd_sesiones SET revoked_at = NOW() WHERE admin_id = $1 AND revoked_at IS NULL", admin_id)
    await _audit(request, admin, "admin_dominio_editar", actual["username"],
                 {"dominios": dominios, "active": activa, "clave_cambiada": bool(nueva_clave)})
    return {"ok": True}


@router.delete("/{admin_id}")
async def eliminar(admin_id: int, request: Request, admin: dict = Depends(require_superadmin)):
    db = _db(request)
    usuario = await db.fetchval("SELECT username FROM pd_admins WHERE id = $1", admin_id)
    if not usuario:
        raise HTTPException(404, "No encontrado")
    await db.execute("DELETE FROM pd_admins WHERE id = $1", admin_id)
    await _audit(request, admin, "admin_dominio_eliminar", usuario)
    return {"ok": True}
