"""Panel · Dispositivos: anclas de red por sede (etapa 1 de la triangulación propia, 22/09/2026).

Subredes o bloques públicos de cada sede con coordenadas fijas. Si un teléfono reporta desde una de
esas redes, el servidor sabe en qué sede está sin GPS. Lectura para todos; alta y baja solo admin.
"""

import ipaddress
import re

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_admin, require_role
from app.dispositivos.comun import auditar, db, texto

router = APIRouter(prefix="/api/dispositivos/anclas", tags=["dispositivos"])
_ADMIN = require_role("superadmin", "admin")
_BSSID = re.compile(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$")


@router.get("")
async def listar(request: Request, admin: dict = Depends(get_current_admin)):
    filas = await db(request).fetch(
        """SELECT a.id, a.tipo, a.valor, a.sede, a.nombre, a.lat, a.lon, a.radio_m, a.activa, a.creado_por, a.creado_en,
                  (SELECT count(*) FROM disp_equipos e WHERE e.ancla_sede = a.sede AND e.ancla_en > NOW() - interval '1 hour') AS equipos_ahora
             FROM disp_anclas_red a ORDER BY a.sede, a.tipo, a.valor""")
    return {"anclas": [dict(f) for f in filas]}


@router.post("")
async def crear(request: Request, admin: dict = Depends(_ADMIN)):
    b = await request.json()
    tipo = b.get("tipo") if b.get("tipo") in ("red", "bssid") else "red"
    valor = (texto(b.get("valor"), 64) or "").lower()
    sede = texto(b.get("sede"), 120)
    if not sede:
        raise HTTPException(400, "Indique la sede")
    if tipo == "red":
        try:
            valor = str(ipaddress.ip_network(valor, strict=False))
        except ValueError:
            raise HTTPException(400, "La red debe ser un CIDR válido, p. ej. 193.16.0.0/24 o 179.49.24.170/32")
    elif not _BSSID.match(valor):
        raise HTTPException(400, "El BSSID debe tener la forma aa:bb:cc:dd:ee:ff")
    try:
        lat, lon = float(b.get("lat")), float(b.get("lon"))
        radio = int(b.get("radio_m") or 60)
    except (TypeError, ValueError):
        raise HTTPException(400, "Latitud, longitud y radio deben ser números")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180 and 5 <= radio <= 5000):
        raise HTTPException(400, "Coordenadas fuera de rango o radio fuera de 5-5000 m")
    fila = await db(request).fetchrow(
        """INSERT INTO disp_anclas_red (tipo, valor, sede, nombre, lat, lon, radio_m, creado_por) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
           ON CONFLICT (tipo, valor) DO UPDATE SET sede = EXCLUDED.sede, nombre = EXCLUDED.nombre, lat = EXCLUDED.lat, lon = EXCLUDED.lon,
               radio_m = EXCLUDED.radio_m, activa = TRUE RETURNING id""",
        tipo, valor, sede, texto(b.get("nombre"), 160) or "", lat, lon, radio, admin["username"])
    await auditar(request, admin, "dispositivo_ancla_guardar", str(fila["id"]), {"tipo": tipo, "valor": valor, "sede": sede, "lat": lat, "lon": lon, "radio_m": radio})
    return {"id": fila["id"]}


@router.delete("/{ancla_id}")
async def borrar(ancla_id: int, request: Request, admin: dict = Depends(_ADMIN)):
    await db(request).execute("DELETE FROM disp_anclas_red WHERE id = $1", ancla_id)
    await auditar(request, admin, "dispositivo_ancla_borrar", str(ancla_id))
    return {"ok": True}
