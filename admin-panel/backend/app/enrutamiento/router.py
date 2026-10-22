"""Enrutamiento de correo por dominio (panel general, Dominios → Enrutamiento).

- MX de respaldo: el servidor acepta y encola el correo de un dominio que vive en otro servidor
  y lo entrega a su MX principal cuando vuelve.
- Reenvío a otro servidor: todo el correo del dominio va a smtp:[servidor]:puerto, con TLS
  obligatorio si se pide.

Postfix lo lee de la base (mapas pgsql-enrutamiento-*.cf, ajuste 68): guardar aquí surte efecto
en la siguiente consulta, sin recargar nada. Un dominio con enrutamiento activo deja de entregar
en los buzones de este servidor.
"""

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_admin, require_role
from app.enrutamiento.validacion import ErrorEnrutamiento, dominio_valido, normalizar, siguiente_salto

router = APIRouter(prefix="/api/enrutamiento", tags=["enrutamiento"])
CAMPOS = "dominio, modo, destino_host, destino_puerto, tls_obligatorio, verificar_destinatarios, activo, actualizado_por, actualizado_en"


async def _audit(r: Request, a: dict, action: str, target: str, details: dict | None = None):
    await r.app.state.db.execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        a["id"], a["username"], action, target, json.dumps(details) if details else None,
        r.headers.get("X-Real-IP", r.client.host if r.client else ""),
    )


async def _postconf(*nombres: str) -> list[str] | None:
    """Valores de Postfix (sin privilegios). None si postconf no está o falla."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "postconf", "-xh", *nombres, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        salida, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
    except (OSError, asyncio.TimeoutError):
        return None
    return salida.decode(errors="replace").splitlines() if proc.returncode == 0 else None


async def _propios() -> set[str]:
    valores = await _postconf("myhostname") or []
    return {v.strip().lower() for v in valores if v.strip()}


async def _dominio(request: Request, dominio: str) -> str:
    try:
        dominio = dominio_valido(dominio)
    except ErrorEnrutamiento as e:
        raise HTTPException(400, str(e))
    if not await request.app.state.db.fetchval("SELECT 1 FROM domain WHERE domain = $1", dominio):
        raise HTTPException(404, "Dominio no encontrado")
    return dominio


@router.get("/estado")
async def estado(admin: dict = Depends(get_current_admin)):
    """¿Tiene Postfix los mapas del enrutamiento? (ajuste 68 o instalación nueva)."""
    valores = await _postconf("relay_domains", "transport_maps")
    if valores is None:
        return {"postfix": None}
    return {"postfix": len(valores) == 2 and all("pgsql-enrutamiento-" in v for v in valores)}


@router.get("/{dominio}")
async def ver(dominio: str, request: Request, admin: dict = Depends(get_current_admin)):
    dominio = await _dominio(request, dominio)
    db = request.app.state.db
    cuentas = await db.fetchval("SELECT count(*) FROM mailbox WHERE domain = $1", dominio)
    fila = await db.fetchrow(f"SELECT {CAMPOS} FROM enrutamiento_correo WHERE dominio = $1", dominio)
    if not fila:
        return {"dominio": dominio, "modo": None, "cuentas_locales": cuentas, "destinatarios": []}
    destinatarios = await db.fetch(
        "SELECT direccion FROM enrutamiento_destinatarios WHERE dominio = $1 ORDER BY direccion", dominio)
    return {**dict(fila), "cuentas_locales": cuentas, "destinatarios": [d["direccion"] for d in destinatarios],
            "siguiente_salto": siguiente_salto(dict(fila))}


@router.put("/{dominio}")
async def guardar(dominio: str, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    dominio = await _dominio(request, dominio)
    datos = await request.json()
    try:
        config = normalizar(dominio, datos, await _propios())
    except ErrorEnrutamiento as e:
        raise HTTPException(400, str(e))
    db = request.app.state.db
    cuentas = await db.fetchval("SELECT count(*) FROM mailbox WHERE domain = $1", dominio)
    if config["activo"] and cuentas and not (isinstance(datos, dict) and datos.get("confirmar_cuentas") is True):
        raise HTTPException(409, f"{dominio} tiene {cuentas} buzón(es) en este servidor: con el enrutamiento activo dejan "
                                 "de recibir correo (va al otro servidor). Confirme para continuar.")
    async with db.acquire() as con, con.transaction():
        await con.execute(
            """INSERT INTO enrutamiento_correo (dominio, modo, destino_host, destino_puerto, tls_obligatorio,
                                                verificar_destinatarios, activo, actualizado_por, actualizado_en)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, now())
               ON CONFLICT (dominio) DO UPDATE SET modo = EXCLUDED.modo, destino_host = EXCLUDED.destino_host,
                   destino_puerto = EXCLUDED.destino_puerto, tls_obligatorio = EXCLUDED.tls_obligatorio,
                   verificar_destinatarios = EXCLUDED.verificar_destinatarios, activo = EXCLUDED.activo,
                   actualizado_por = EXCLUDED.actualizado_por, actualizado_en = now()""",
            dominio, config["modo"], config["destino_host"], config["destino_puerto"], config["tls_obligatorio"],
            config["verificar_destinatarios"], config["activo"], admin["username"])
        await con.execute("DELETE FROM enrutamiento_destinatarios WHERE dominio = $1", dominio)
        if config["destinatarios"]:
            await con.executemany(
                "INSERT INTO enrutamiento_destinatarios (direccion, dominio) VALUES ($1, $2)",
                [(d, dominio) for d in config["destinatarios"]])
    detalles = {k: config[k] for k in ("modo", "destino_host", "destino_puerto", "tls_obligatorio",
                                       "verificar_destinatarios", "activo")}
    await _audit(request, admin, "enrutamiento_guardar", dominio,
                 {**detalles, "destinatarios": len(config["destinatarios"]), "cuentas_locales": cuentas})
    return await ver(dominio, request, admin)


@router.delete("/{dominio}")
async def quitar(dominio: str, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    dominio = await _dominio(request, dominio)
    r = await request.app.state.db.execute("DELETE FROM enrutamiento_correo WHERE dominio = $1", dominio)
    if r != "DELETE 1":
        raise HTTPException(404, "El dominio no tiene enrutamiento")
    await _audit(request, admin, "enrutamiento_quitar", dominio)
    return {"ok": True, "dominio": dominio}
