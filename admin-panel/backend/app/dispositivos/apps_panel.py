"""Panel · Dispositivos (fase 4): inventario de apps por equipo, reglas globales y comandos de app."""

import json

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_admin, require_role
from app.dispositivos.comun import auditar, db, texto
from app.dispositivos.perdido import _encolar, _equipo, _motivo

router = APIRouter(prefix="/api/dispositivos", tags=["dispositivos"])
_ADMIN = require_role("superadmin", "admin")


@router.get("/equipos/{equipo_id}/apps")
async def apps_de(equipo_id: int, request: Request, admin: dict = Depends(get_current_admin)):
    filas = await db(request).fetch(
        "SELECT paquete, nombre, version, instalador, firma_sha256, permisos, sistema, veredicto, motivo, primera_vez, vista_en "
        "FROM disp_apps WHERE equipo_id = $1 ORDER BY (veredicto <> 'ok') DESC, sistema, nombre", equipo_id)
    def _j(v):
        return json.loads(v) if isinstance(v, str) else v
    return {"apps": [{**dict(f), "permisos": _j(f["permisos"])} for f in filas]}


@router.post("/equipos/{equipo_id}/apps/{paquete}/comando")
async def comando_app(equipo_id: int, paquete: str, request: Request, admin: dict = Depends(_ADMIN)):
    """Pide a un equipo con control completo desinstalar o bloquear una app concreta."""
    b = await request.json()
    accion = b.get("accion")
    if accion not in ("desinstalar", "bloquear_app"):
        raise HTTPException(400, "Acción no admitida")
    e = await _equipo(request, equipo_id)
    if e["modo"] != "propietario":
        raise HTTPException(409, "El equipo está en modo limitado: solo se puede avisar a la persona, no desinstalar a distancia")
    motivo = _motivo(b)
    async with db(request).acquire() as con:
        cid = await _encolar(con, equipo_id, accion, {"paquete": paquete[:255]}, admin, motivo)
    await auditar(request, admin, f"dispositivo_app_{accion}", str(equipo_id), {"paquete": paquete, "motivo": motivo})
    return {"id": cid}


@router.get("/apps-reglas")
async def listar_reglas(request: Request, admin: dict = Depends(get_current_admin)):
    filas = await db(request).fetch(
        "SELECT id, tipo, valor, accion, nota, creado_por, creado_en FROM disp_apps_reglas ORDER BY tipo, valor")
    resumen = await db(request).fetch(
        "SELECT count(DISTINCT equipo_id) FILTER (WHERE veredicto='bloqueada') AS con_bloqueada, "
        "count(DISTINCT equipo_id) FILTER (WHERE veredicto='sospechosa') AS con_sospechosa FROM disp_apps")
    return {"reglas": [dict(f) for f in filas], "resumen": dict(resumen[0])}


@router.post("/apps-reglas")
async def crear_regla(request: Request, admin: dict = Depends(_ADMIN)):
    b = await request.json()
    tipo = b.get("tipo")
    if tipo not in ("paquete", "firma", "permiso", "instalador"):
        raise HTTPException(400, "Tipo inválido")
    accion = b.get("accion") if b.get("accion") in ("avisar", "bloquear", "permitir") else "avisar"
    valor = texto(b.get("valor"), 255)
    if not valor:
        raise HTTPException(400, "Indique el valor (paquete, firma, permiso o instalador)")
    try:
        rid = await db(request).fetchval(
            "INSERT INTO disp_apps_reglas (tipo, valor, accion, nota, creado_por) VALUES ($1,$2,$3,$4,$5) RETURNING id",
            tipo, valor, accion, texto(b.get("nota"), 255), admin["username"])
    except Exception:
        raise HTTPException(409, "Ya existe una regla para ese valor")
    await auditar(request, admin, "dispositivo_app_regla_crear", str(rid), {"tipo": tipo, "valor": valor, "accion": accion})
    return {"id": rid}


@router.delete("/apps-reglas/{regla_id}")
async def borrar_regla(regla_id: int, request: Request, admin: dict = Depends(_ADMIN)):
    r = await db(request).fetchrow("SELECT creado_por FROM disp_apps_reglas WHERE id = $1", regla_id)
    if r and r["creado_por"] == "sistema":
        raise HTTPException(409, "Las reglas base del sistema no se borran; cree una regla 'permitir' que la anule si hace falta")
    await db(request).execute("DELETE FROM disp_apps_reglas WHERE id = $1", regla_id)
    await auditar(request, admin, "dispositivo_app_regla_borrar", str(regla_id))
    return {"ok": True}
