"""Panel · Dispositivos (fase 3): estado de los respaldos de cada equipo y autorización de
restauraciones. El panel **no ve el contenido ni los nombres de archivo**: solo fechas, tamaños y
totales por categoría. El contenido está cifrado y solo lo descarga un teléfono: el mismo equipo, u
otro con una autorización temporal creada aquí (con motivo y auditoría).
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_admin, require_role
from app.dispositivos.comun import auditar, db, texto
from app.dispositivos.perdido import _encolar, _equipo, _motivo

router = APIRouter(prefix="/api/dispositivos", tags=["dispositivos"])
_ADMIN = require_role("superadmin", "admin")


@router.get("/equipos/{equipo_id}/respaldos")
async def respaldos_de(equipo_id: int, request: Request, admin: dict = Depends(get_current_admin)):
    d = db(request)
    e = await d.fetchrow("SELECT respaldo_activo, cuota_respaldo_gb, respaldo_cierre_en, carpeta_respaldo FROM disp_equipos WHERE id = $1", equipo_id)
    if e is None:
        raise HTTPException(404, "Equipo no encontrado")
    filas = await d.fetch(
        "SELECT id, tipo, estado, iniciado_en, cerrado_en, archivos_total, bytes_total, archivos_nuevos, bytes_nuevos, faltantes, "
        "resumen, errores, version_app FROM disp_respaldos WHERE equipo_id = $1 ORDER BY iniciado_en DESC LIMIT 30", equipo_id)
    usado = await d.fetchval("SELECT COALESCE(SUM(tamano), 0) FROM disp_objetos WHERE equipo_id = $1 AND estado = 'completo'", equipo_id)
    restauraciones = await d.fetch(
        """SELECT r.id, r.destino_id, r.origen_id, o.nombre AS origen_nombre, o.modelo AS origen_modelo, t.nombre AS destino_nombre,
                  t.modelo AS destino_modelo, r.autorizado_por, r.motivo, r.creado_en, r.caduca_en, r.anulada_en
           FROM disp_restauraciones r JOIN disp_equipos o ON o.id = r.origen_id JOIN disp_equipos t ON t.id = r.destino_id
           WHERE r.destino_id = $1 OR r.origen_id = $1 ORDER BY r.creado_en DESC LIMIT 20""", equipo_id)

    def _j(v):
        return json.loads(v) if isinstance(v, str) else v
    return {
        **dict(e), "usado_bytes": int(usado),
        "respaldos": [{**dict(f), "resumen": _j(f["resumen"]), "errores": _j(f["errores"])} for f in filas],
        "restauraciones": [dict(r) for r in restauraciones],
    }


@router.put("/equipos/{equipo_id}/respaldo-config")
async def configurar(equipo_id: int, request: Request, admin: dict = Depends(_ADMIN)):
    b = await request.json()
    cuota = int(b.get("cuota_respaldo_gb") or 64)
    if not 1 <= cuota <= 2048:
        raise HTTPException(400, "La cuota debe estar entre 1 y 2048 GB")
    await _equipo(request, equipo_id)
    carpeta = texto(b.get("carpeta_respaldo"), 80)
    import re as _re
    if carpeta is not None and not _re.fullmatch(r"[A-Za-z0-9._-]{1,80}", carpeta):
        raise HTTPException(400, "La carpeta de respaldo solo admite letras, números, punto, guion y guion bajo")
    if carpeta is not None and await db(request).fetchval("SELECT 1 FROM disp_objetos WHERE equipo_id = $1 LIMIT 1", equipo_id):
        raise HTTPException(409, "No se puede cambiar la carpeta: el equipo ya tiene respaldos. Cámbiela solo antes del primero.")
    await db(request).execute("UPDATE disp_equipos SET respaldo_activo = $2, cuota_respaldo_gb = $3, carpeta_respaldo = COALESCE($4, carpeta_respaldo) WHERE id = $1",
                              equipo_id, bool(b.get("respaldo_activo", True)), cuota, carpeta)
    await auditar(request, admin, "dispositivo_respaldo_config", str(equipo_id), {"activo": bool(b.get("respaldo_activo", True)), "cuota_gb": cuota, "carpeta": carpeta})
    return {"ok": True}


@router.post("/equipos/{equipo_id}/respaldar")
async def pedir_respaldo(equipo_id: int, request: Request, admin: dict = Depends(_ADMIN)):
    """Encola el comando `respaldar`. Con tipo `cierre` es el respaldo previo a reasignar o restablecer."""
    b = await request.json()
    tipo = b.get("tipo") if b.get("tipo") in ("manual", "cierre") else "manual"
    await _equipo(request, equipo_id)
    motivo = _motivo(b)
    async with db(request).acquire() as con:
        cid = await _encolar(con, equipo_id, "respaldar", {"tipo": tipo}, admin, motivo)
    await auditar(request, admin, "dispositivo_comando_respaldar", str(equipo_id), {"tipo": tipo, "motivo": motivo})
    return {"id": cid}


@router.post("/equipos/{destino_id}/autorizar-restauracion")
async def autorizar_restauracion(destino_id: int, request: Request, admin: dict = Depends(_ADMIN)):
    """Permite que `destino` (teléfono nuevo) descargue durante un tiempo los respaldos de `origen`."""
    b = await request.json()
    try:
        origen_id = int(b.get("origen_id"))
    except (TypeError, ValueError):
        raise HTTPException(400, "Indique el equipo de origen")
    if origen_id == destino_id:
        raise HTTPException(400, "Un equipo siempre puede restaurar sus propios respaldos")
    await _equipo(request, destino_id)
    d = db(request)
    if not await d.fetchval("SELECT 1 FROM disp_respaldos WHERE equipo_id = $1 AND estado = 'completo' LIMIT 1", origen_id):
        raise HTTPException(409, "El equipo de origen no tiene ningún respaldo completo")
    motivo = _motivo(b)
    horas = int(b.get("horas") or 72)
    if not 1 <= horas <= 168:
        raise HTTPException(400, "La autorización dura entre 1 hora y 7 días")
    rid = await d.fetchval(
        "INSERT INTO disp_restauraciones (destino_id, origen_id, autorizado_por, motivo, caduca_en) "
        "VALUES ($1,$2,$3,$4, NOW() + make_interval(hours => $5)) RETURNING id", destino_id, origen_id, admin["username"], motivo, horas)
    await auditar(request, admin, "dispositivo_restauracion_autorizar", str(destino_id), {"origen": origen_id, "motivo": motivo, "horas": horas})
    return {"id": rid}


@router.delete("/restauraciones/{rid}")
async def anular_restauracion(rid: int, request: Request, admin: dict = Depends(_ADMIN)):
    await db(request).execute("UPDATE disp_restauraciones SET anulada_en = NOW() WHERE id = $1 AND anulada_en IS NULL", rid)
    await auditar(request, admin, "dispositivo_restauracion_anular", str(rid))
    return {"ok": True}
