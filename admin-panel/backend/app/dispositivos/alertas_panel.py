"""Panel · Dispositivos: alertas automáticas de telemetría y sus umbrales (AE-03).

Las alertas las abre y cierra el trabajo `maquita-disp-alertas.timer` (backend del correo, cada 15 min)
según `disp_config.alertas`. Aquí se listan (rol lector incluido) y se editan los umbrales (solo admin).
"""

import json
import re

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_admin, require_role
from app.dispositivos.comun import auditar, db

router = APIRouter(prefix="/api/dispositivos/alertas", tags=["dispositivos"])
_ADMIN = require_role("superadmin", "admin")

# clave: (mínimo, máximo)
_NUMEROS = {"sin_reportar_horas": (1, 720), "bateria_pct": (1, 60), "bateria_horas": (1, 72), "almacenamiento_pct": (1, 50),
            "version_atrasada_dias": (0, 365), "acuse_horas": (1, 168)}
_CORREOS = re.compile(r"^[^@\s,]+@[^@\s,]+\.[^@\s,]+$")


async def _config(request: Request) -> dict:
    v = await db(request).fetchval("SELECT valor FROM disp_config WHERE clave = 'alertas'")
    return (json.loads(v) if isinstance(v, str) else v) or {}


@router.get("")
async def listar(request: Request, abiertas: bool = True, admin: dict = Depends(get_current_admin)):
    filas = await db(request).fetch(
        f"""SELECT a.id, a.equipo_id, a.tipo, a.detalle, a.desde, a.hasta, a.avisada_en,
                   e.nombre, e.fabricante, e.modelo, e.custodio_nombre, e.custodio_email, e.sede
              FROM disp_alertas a JOIN disp_equipos e ON e.id = a.equipo_id
             {"WHERE a.hasta IS NULL" if abiertas else "WHERE a.desde > NOW() - interval '30 days'"}
             ORDER BY a.hasta NULLS FIRST, a.desde DESC LIMIT 500""")
    estado = await db(request).fetchval("SELECT valor FROM disp_config WHERE clave = 'alertas_estado'")
    return {
        "alertas": [{**dict(f), "detalle": json.loads(f["detalle"]) if isinstance(f["detalle"], str) else f["detalle"]} for f in filas],
        "config": await _config(request),
        "estado": (json.loads(estado) if isinstance(estado, str) else estado) or {},
    }


@router.put("/config")
async def guardar_config(request: Request, admin: dict = Depends(_ADMIN)):
    b = await request.json()
    actual = await _config(request)
    nuevo = dict(actual)
    for k, (lo, hi) in _NUMEROS.items():
        if k in b:
            try:
                v = int(b[k])
            except (TypeError, ValueError):
                raise HTTPException(400, f"«{k}» debe ser un número")
            if not lo <= v <= hi:
                raise HTTPException(400, f"«{k}» debe estar entre {lo} y {hi}")
            nuevo[k] = v
    for k in ("correo_ti", "resumen_diario_para"):
        if k in b:
            correos = [c.strip().lower() for c in str(b[k] or "").split(",") if c.strip()]
            malos = [c for c in correos if not _CORREOS.match(c)]
            if malos:
                raise HTTPException(400, f"Correo no válido: {', '.join(malos)}")
            nuevo[k] = ", ".join(correos)
    if "resumen_hora" in b:
        h = str(b["resumen_hora"] or "07:30")
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", h):
            raise HTTPException(400, "La hora del resumen debe ser HH:MM")
        nuevo["resumen_hora"] = h
    if "activo" in b:
        nuevo["activo"] = bool(b["activo"])
    if not nuevo.get("correo_ti"):
        raise HTTPException(400, "Hace falta al menos un correo de Tecnología para avisar")
    await db(request).execute(
        "INSERT INTO disp_config (clave, valor) VALUES ('alertas', $1::jsonb) "
        "ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor, actualizado_en = NOW()", json.dumps(nuevo))
    await auditar(request, admin, "dispositivo_alertas_config", "alertas", {k: v for k, v in nuevo.items() if actual.get(k) != v})
    return {"ok": True, "config": nuevo}
