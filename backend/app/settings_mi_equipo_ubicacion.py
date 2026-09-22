"""«Teléfono extraviado» en Configuración → «Mi teléfono» del correo web (22/09/2026, pedido de dirección).

La persona ve, sin nada técnico, la **última ubicación conocida** de cada teléfono institucional del
que es custodia (la más precisa de los últimos 15 minutos respecto a la más reciente), con su margen en
palabras y enlaces para verla en un mapa; y puede pedir «Ubicar ahora» y «Hacer sonar».

Reglas:
- Solo el custodio autenticado ve sus propios teléfonos (filtro por `custodio_email`).
- Solo se muestran posiciones que el servidor guardó según la regla de la fase 2 (ubicación autorizada
  por firma de la política o equipo declarado perdido). Si no hay ninguna, se explica por qué.
- «Ubicar ahora» y «Hacer sonar» encolan el mismo comando que el panel (con push) y quedan en
  `admin_audit` como pedidos del custodio (`admin_id` NULL), con límite de uno por minuto.
"""

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_user
from app.dispositivos import push_ntfy

logger = logging.getLogger("dispositivos")
router = APIRouter(prefix="/api/settings/mi-equipo", tags=["mi-equipo"])
_VENTANA_MIN = 15


def _margen(p: dict) -> str:
    m = p.get("precision_m")
    if p.get("origen") == "avistamiento":
        return "cerca de otro teléfono de Maquita"
    if p.get("origen") == "ancla":
        return "en la oficina (conectado a la red de Maquita)"
    if m is None:
        return "margen desconocido"
    m = int(round(m))
    if m >= 1000:
        return f"margen de unos {m / 1000:.1f} km (solo el sector)"
    return f"margen de unos {m} m"


async def _mis_equipos(db, username: str) -> list[dict]:
    filas = await db.fetch(
        "SELECT id, nombre, modelo, fabricante, estado, modo, ultimo_contacto, ubicacion_autorizada, push_topic, wifi_ssid, wifi_en, red "
        "FROM disp_equipos WHERE custodio_email = $1 AND estado IN ('activo', 'perdido') ORDER BY enrolado_en DESC",
        username,
    )
    return [dict(f) for f in filas]


async def _mejor_posicion(db, equipo_id: int) -> dict | None:
    filas = await db.fetch(
        "SELECT tomada_en, lat, lon, precision_m, origen FROM disp_ubicaciones WHERE equipo_id = $1 "
        "ORDER BY tomada_en DESC LIMIT 40",
        equipo_id,
    )
    if not filas:
        return None
    t0 = filas[0]["tomada_en"]
    candidatas = [dict(f) for f in filas if (t0 - f["tomada_en"]).total_seconds() <= _VENTANA_MIN * 60 and f["origen"] != "avistamiento"]
    mejor = min(candidatas or [dict(filas[0])], key=lambda p: p["precision_m"] if p["precision_m"] is not None else 1e9)
    return {
        "lat": mejor["lat"], "lon": mejor["lon"], "precision_m": mejor["precision_m"],
        "cuando": mejor["tomada_en"].isoformat(), "margen": _margen(mejor),
        "minutos": int((datetime.now(timezone.utc) - mejor["tomada_en"]).total_seconds() // 60),
    }


@router.get("/ubicacion")
async def ubicacion(request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    salida = []
    for e in await _mis_equipos(db, username):
        pendiente = await db.fetchval(
            "SELECT count(*) FROM disp_comandos WHERE equipo_id = $1 AND tipo = 'localizar' AND estado IN ('pendiente', 'entregado')", e["id"])
        salida.append({
            "id": e["id"],
            "nombre": e["nombre"] or f"{e['fabricante'] or ''} {e['modelo'] or 'Teléfono'}".strip(),
            "estado": e["estado"],
            "ultimo_contacto": e["ultimo_contacto"].isoformat() if e["ultimo_contacto"] else None,
            "ubicacion_permitida": bool(e["ubicacion_autorizada"]) or e["estado"] == "perdido",
            "posicion": await _mejor_posicion(db, e["id"]),
            # Nombre del wifi al que está conectado (si la app lo manda y el último reporte fue por wifi).
            "wifi": e["wifi_ssid"] if e["wifi_ssid"] and (e["red"] or "").lower().find("wifi") >= 0 else None,
            "wifi_en": e["wifi_en"].isoformat() if e["wifi_ssid"] and e["wifi_en"] else None,
            "buscando": pendiente > 0,
        })
    return {"equipos": salida}


async def _comando(request: Request, username: str, equipo_id: int, tipo: str) -> dict:
    db = request.app.state.db_pool
    e = await db.fetchrow(
        "SELECT id, estado, push_topic FROM disp_equipos WHERE id = $1 AND custodio_email = $2 AND estado IN ('activo', 'perdido')",
        equipo_id, username)
    if e is None:
        raise HTTPException(404, "Ese teléfono no está a tu nombre")
    reciente = await db.fetchval(
        "SELECT 1 FROM disp_comandos WHERE equipo_id = $1 AND tipo = $2 AND creado_por = $3 AND creado_en > NOW() - interval '1 minute'",
        equipo_id, tipo, username)
    if reciente:
        raise HTTPException(429, "Ya lo pediste hace menos de un minuto; espera la respuesta del teléfono")
    async with db.acquire() as con, con.transaction():
        cid = await con.fetchval(
            "SELECT id FROM disp_comandos WHERE equipo_id = $1 AND tipo = $2 AND estado = 'pendiente'", equipo_id, tipo)
        if not cid:
            cid = await con.fetchval(
                "INSERT INTO disp_comandos (equipo_id, tipo, parametros, creado_por, motivo) VALUES ($1,$2,'{}'::jsonb,$3,$4) RETURNING id",
                equipo_id, tipo, username, "Pedido por el custodio desde Configuración → Mi teléfono")
        await con.execute(
            "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) "
            "VALUES (NULL, $1, $2, $3, $4::jsonb, $5)",
            username, f"dispositivo_custodio_{tipo}", str(equipo_id), json.dumps({"comando": cid}),
            request.headers.get("X-Real-IP", request.client.host if request.client else ""))
    push_ntfy.avisar(e["push_topic"], "comando")
    return {"ok": True, "comando": cid}


@router.post("/{equipo_id}/localizar")
async def localizar(equipo_id: int, request: Request, username: str = Depends(get_current_user)):
    """Pide al teléfono su posición ahora. Solo se guardará (y verá) si la ubicación está permitida."""
    return await _comando(request, username, equipo_id, "localizar")


@router.post("/{equipo_id}/sonar")
async def sonar(equipo_id: int, request: Request, username: str = Depends(get_current_user)):
    return await _comando(request, username, equipo_id, "alarma")
