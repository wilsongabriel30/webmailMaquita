"""Wifi de las sedes compartido con la flota (22/09/2026, pedido de dirección).

Los compañeros viajan entre sedes y pelean con las claves del wifi. Tecnología registra el wifi de cada
sede en el panel; cada teléfono enrolado recibe la lista (`GET /api/dispositivos/wifis`, con su token)
y la app las agrega como redes sugeridas para conectarse sola al llegar. La respuesta del latido trae
`wifis_version`: cuando sube, la app vuelve a pedir la lista.

Si una clave cambió y un teléfono la corrigió y **logró conectarse**, la app avisa con
`POST /api/dispositivos/wifis/{id}/clave` y el servidor la replica al resto (sube la versión y anota
quién la corrigió). Las claves viajan solo a teléfonos enrolados, por HTTPS, y en la base van cifradas.
"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.dispositivos.codigo_cifrado import cifrar, descifrar
from app.dispositivos.seguridad import equipo_actual, limitar

logger = logging.getLogger("dispositivos")
router = APIRouter(prefix="/api/dispositivos/wifis", tags=["dispositivos"])


async def version(db) -> int:
    try:
        v = await db.fetchval("SELECT valor->>'version' FROM disp_config WHERE clave = 'wifis'")
        return int(v or 1)
    except Exception:
        return 1


async def subir_version(db) -> int:
    v = await version(db) + 1
    await db.execute(
        "INSERT INTO disp_config (clave, valor) VALUES ('wifis', $1::jsonb) "
        "ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor, actualizado_en = NOW()", json.dumps({"version": v}))
    return v


@router.get("")
async def listar(request: Request, equipo: dict = Depends(equipo_actual)):
    """Lista completa con claves en claro para el teléfono enrolado."""
    await limitar(request, f"wifis:{equipo['id']}", 30, 3600)
    db = request.app.state.db_pool
    filas = await db.fetch("SELECT id, sede, ssid, clave_cifrada, seguridad, oculta, version FROM disp_wifis WHERE activa ORDER BY sede, ssid")
    return {
        "version": await version(db),
        "redes": [{"id": f["id"], "sede": f["sede"], "ssid": f["ssid"], "clave": descifrar(f["clave_cifrada"]) if f["clave_cifrada"] else None,
                   "seguridad": f["seguridad"], "oculta": f["oculta"], "version": f["version"]} for f in filas],
    }


class ClaveCorregida(BaseModel):
    clave: str = Field(..., min_length=8, max_length=63)
    bssid: str | None = Field(None, pattern=r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
    conectado: bool = True   # solo se acepta si el teléfono se conectó de verdad con esa clave


@router.post("/{wifi_id}/clave")
async def clave_corregida(wifi_id: int, request: Request, body: ClaveCorregida, equipo: dict = Depends(equipo_actual)):
    await limitar(request, f"wifis_clave:{equipo['id']}", 5, 3600)
    if not body.conectado:
        raise HTTPException(400, "Solo se replica una clave con la que el teléfono logró conectarse")
    db = request.app.state.db_pool
    w = await db.fetchrow("SELECT id, ssid, sede, clave_cifrada FROM disp_wifis WHERE id = $1 AND activa", wifi_id)
    if w is None:
        raise HTTPException(404, "Red no encontrada")
    if w["clave_cifrada"] and descifrar(w["clave_cifrada"]) == body.clave:
        return {"ok": True, "version": await version(db), "sin_cambio": True}
    cifrada = cifrar(body.clave)
    if not cifrada:
        raise HTTPException(503, "El servidor no tiene clave de cifrado configurada")
    async with db.acquire() as con, con.transaction():
        await con.execute(
            "UPDATE disp_wifis SET clave_cifrada = $2, version = version + 1, actualizado_por = $3, actualizado_en = NOW() WHERE id = $1",
            wifi_id, cifrada, f"equipo {equipo['id']}")
        await con.execute(
            "INSERT INTO disp_wifis_cambios (wifi_id, origen, quien, equipo_id, detalle) VALUES ($1, 'telefono', $2, $3, $4)",
            wifi_id, equipo.get("custodio_email") or f"equipo {equipo['id']}", equipo["id"],
            f"Clave corregida desde el teléfono ({equipo.get('nombre') or 'sin nombre'}); conectado a {body.bssid or w['ssid']}")
        v = await subir_version(con)
    logger.info("wifi_clave_corregida | wifi=%s | equipo=%s", wifi_id, equipo["id"])
    return {"ok": True, "version": v}


class RedCompartida(BaseModel):
    """Red a la que el teléfono se conectó (y la persona aceptó compartir con los compañeros)."""
    ssid: str = Field(..., min_length=1, max_length=32)
    clave: str | None = Field(None, min_length=8, max_length=63)
    seguridad: str = Field("WPA", pattern=r"^(WPA|WPA3|NONE)$")
    bssid: str | None = Field(None, pattern=r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
    lugar: str | None = Field(None, max_length=120)   # «Evento X», «Hotel Y»: lo escribe la persona o lo infiere la app
    oculta: bool = False


@router.post("/compartir")
async def compartir(request: Request, body: RedCompartida, equipo: dict = Depends(equipo_actual)):
    """Un teléfono conectado a una red la comparte con toda la flota (eventos, hoteles, aliados).
    Si ya existe con ese nombre, actualiza la clave solo si cambió. Nunca pisa una red de sede del panel
    salvo la clave (que sí se replica, como en /{id}/clave)."""
    await limitar(request, f"wifis_compartir:{equipo['id']}", 20, 86400)
    if body.seguridad != "NONE" and not body.clave:
        raise HTTPException(400, "Falta la clave de la red")
    db = request.app.state.db_pool
    quien = equipo.get("custodio_email") or f"equipo {equipo['id']}"
    lugar = (body.lugar or "").strip() or (equipo.get("ancla_sede") or "Compartida por un compañero")
    cifrada = cifrar(body.clave) if body.clave and body.seguridad != "NONE" else None
    if body.clave and body.seguridad != "NONE" and not cifrada:
        raise HTTPException(503, "El servidor no tiene clave de cifrado configurada")
    async with db.acquire() as con, con.transaction():
        existente = await con.fetchrow("SELECT id, clave_cifrada, sede FROM disp_wifis WHERE ssid = $1 ORDER BY (origen = 'panel') DESC, id LIMIT 1", body.ssid)
        if existente:
            misma = (existente["clave_cifrada"] and descifrar(existente["clave_cifrada"]) == body.clave) or (not existente["clave_cifrada"] and not body.clave)
            await con.execute("UPDATE disp_wifis SET ultimo_uso = NOW(), bssid = COALESCE($2, bssid), activa = TRUE WHERE id = $1", existente["id"], body.bssid)
            if misma:
                return {"ok": True, "id": existente["id"], "version": await version(con), "sin_cambio": True}
            await con.execute("UPDATE disp_wifis SET clave_cifrada = $2, version = version + 1, actualizado_por = $3, actualizado_en = NOW() WHERE id = $1",
                              existente["id"], cifrada, quien)
            await con.execute("INSERT INTO disp_wifis_cambios (wifi_id, origen, quien, equipo_id, detalle) VALUES ($1, 'telefono', $2, $3, $4)",
                              existente["id"], quien, equipo["id"], "Clave actualizada por un teléfono que se conectó con la nueva")
            wid = existente["id"]
        else:
            wid = await con.fetchval(
                """INSERT INTO disp_wifis (sede, ssid, clave_cifrada, seguridad, oculta, nota, actualizado_por, origen, compartida_por, equipo_id, bssid, ultimo_uso)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, 'telefono', $7, $8, $9, NOW()) RETURNING id""",
                lugar[:120], body.ssid, cifrada, body.seguridad, body.oculta, f"Compartida desde el teléfono de {quien}"[:160], quien, equipo["id"], body.bssid)
            await con.execute("INSERT INTO disp_wifis_cambios (wifi_id, origen, quien, equipo_id, detalle) VALUES ($1, 'telefono', $2, $3, 'Red compartida con la flota')",
                              wid, quien, equipo["id"])
        v = await subir_version(con)
    logger.info("wifi_compartida | wifi=%s | equipo=%s | ssid=%s", wid, equipo["id"], body.ssid)
    return {"ok": True, "id": wid, "version": v}
