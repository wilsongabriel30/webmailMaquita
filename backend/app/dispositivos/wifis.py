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
