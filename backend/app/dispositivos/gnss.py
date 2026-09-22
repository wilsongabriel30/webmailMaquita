"""Lotes de mediciones GNSS crudas de los teléfonos (etapa 3, experimento REGME, 22/09/2026).

La app registra unos segundos de mediciones crudas de satélite (formato de texto del GnssLogger) y las
manda aquí. El servidor solo las guarda en disco (`DISP_GNSS_DIR`) y anota el lote en `disp_gnss_lotes`;
el procesamiento (conversión a RINEX + corrección diferencial contra la estación REGME más cercana con
RTKLIB) se hace fuera de línea y su resultado se escribe en `resultado`. Si la mejora es real, la
posición corregida entrará en `disp_ubicaciones` como una fuente más, con su margen.
"""

import base64
import gzip
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.dispositivos.seguridad import equipo_actual, ip_cliente, limitar

logger = logging.getLogger("dispositivos")
router = APIRouter(prefix="/api/dispositivos/gnss", tags=["dispositivos"])
DIR = Path(os.environ.get("DISP_GNSS_DIR", "/var/lib/maquita-webmail/gnss"))
MAX_BYTES = 8 * 1024 * 1024


class Fix(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)
    precision: Optional[float] = Field(None, ge=0)


class LoteGnss(BaseModel):
    inicio: str = Field(..., max_length=40)
    fin: str = Field(..., max_length=40)
    segundos: int = Field(..., ge=1, le=900)
    formato: str = Field("gnsslogger-txt", max_length=32)
    modelo: Optional[str] = Field(None, max_length=120)
    android: Optional[str] = Field(None, max_length=40)
    capacidades: Optional[dict] = None
    fix: Optional[Fix] = None
    datos_gz: str = Field(..., min_length=16)  # base64 de gzip del texto


@router.post("")
async def recibir(request: Request, body: LoteGnss, equipo: dict = Depends(equipo_actual)):
    await limitar(request, f"gnss:{equipo['id']}", 20, 3600)
    try:
        comprimido = base64.b64decode(body.datos_gz, validate=True)
    except Exception:
        raise HTTPException(400, "datos_gz no es base64 válido")
    if len(comprimido) > MAX_BYTES:
        raise HTTPException(413, "Lote demasiado grande (máximo 8 MB)")
    try:
        texto = gzip.decompress(comprimido)
    except Exception:
        raise HTTPException(400, "datos_gz no es gzip válido")
    if len(texto) > 4 * MAX_BYTES or b"Raw," not in texto:
        raise HTTPException(400, "El lote no tiene líneas «Raw,» del formato GnssLogger")
    carpeta = DIR / str(equipo["id"])
    carpeta.mkdir(parents=True, exist_ok=True)
    nombre = datetime.utcnow().strftime("%Y%m%d-%H%M%S") + ".txt.gz"
    (carpeta / nombre).write_bytes(comprimido)
    lote_id = await request.app.state.db_pool.fetchval(
        """INSERT INTO disp_gnss_lotes (equipo_id, inicio, fin, segundos, formato, modelo, android, capacidades, fix, archivo, bytes, ip)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb, $10, $11, $12) RETURNING id""",
        equipo["id"], body.inicio[:40], body.fin[:40], body.segundos, body.formato, body.modelo, body.android,
        json.dumps(body.capacidades or {}), json.dumps(body.fix.model_dump() if body.fix else None),
        str(carpeta / nombre), len(comprimido), ip_cliente(request),
    )
    logger.info("gnss_lote | equipo=%s | id=%s | bytes=%d | segundos=%d", equipo["id"], lote_id, len(comprimido), body.segundos)
    return {"id": lote_id, "bytes": len(comprimido)}
