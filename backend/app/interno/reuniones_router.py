"""Rutas internas: evento del calendario del correo de una reunión de Raíces (04/11/2026).

- POST /api/interno/reuniones/evento           crea o actualiza (idempotente) el evento de la reunión
- POST /api/interno/reuniones/evento/cancelar  quita el evento (idempotente)

Solo con el token de servicio y desde una IP permitida (ver acceso_servicio.py). Cada llamada queda en el
registro `maquita.webmail.interno.reuniones` (journal de maquita-webmail) (operación, reunión, organizador, IP y resultado).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.interno import reuniones_evento as rev
from app.interno.acceso_servicio import exigir_servicio_reuniones

router = APIRouter(prefix="/api/interno/reuniones", tags=["interno"])
log = logging.getLogger("maquita.webmail.interno.reuniones")
_CORREO = re.compile(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$")


def _correo(v: str) -> str:
    v = (v or "").strip().lower()
    if not _CORREO.match(v) or len(v) > 255:
        raise ValueError("correo no válido")
    return v


class ReunionRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reunion_id: int = Field(gt=0, lt=2**31)
    organizador: str

    @field_validator("organizador")
    @classmethod
    def _org(cls, v):
        return _correo(v)


class EventoReunion(ReunionRef):
    asunto: str = Field(min_length=1, max_length=200)
    inicio: datetime
    duracion_horas: int = Field(ge=1, le=12)
    participantes: list[str] = Field(default_factory=list, max_length=200)
    mensaje: str = Field(default="", max_length=1000)
    sala: str = Field(pattern=r"^[A-Za-z0-9_\-]{3,120}$")

    @field_validator("participantes")
    @classmethod
    def _part(cls, v):
        return [_correo(x) for x in v if (x or "").strip()]


def _db(request: Request):
    return request.app.state.db_pool


async def _organizador_valido(db, org: str, op: str, rid: int, ip: str) -> None:
    if not await rev.es_buzon_activo(db, org):
        log.warning(
            "INTERNO_REUNIONES op=%s reunion=%s organizador=%s ip=%s resultado=sin_buzon",
            op,
            rid,
            org,
            ip,
        )
        raise HTTPException(404, "El organizador no tiene buzón activo en el correo")


@router.post("/evento")
async def sincronizar_evento(
    datos: EventoReunion, request: Request, ip: str = Depends(exigir_servicio_reuniones)
):
    db = _db(request)
    await _organizador_valido(
        db, datos.organizador, "sincronizar", datos.reunion_id, ip
    )
    try:
        res = await rev.sincronizar(db, **datos.model_dump())
    except ValueError as e:
        log.warning(
            "INTERNO_REUNIONES op=sincronizar reunion=%s organizador=%s ip=%s resultado=error %s",
            datos.reunion_id,
            datos.organizador,
            ip,
            str(e)[:120],
        )
        raise HTTPException(400, "No se pudo guardar el evento")
    log.info(
        "INTERNO_REUNIONES op=sincronizar reunion=%s organizador=%s ip=%s resultado=%s evento=%s",
        datos.reunion_id,
        datos.organizador,
        ip,
        res["accion"],
        res["evento_id"],
    )
    return {"success": True, **res}


@router.post("/evento/cancelar")
async def cancelar_evento(
    datos: ReunionRef, request: Request, ip: str = Depends(exigir_servicio_reuniones)
):
    db = _db(request)
    await _organizador_valido(db, datos.organizador, "cancelar", datos.reunion_id, ip)
    res = await rev.cancelar(
        db, reunion_id=datos.reunion_id, organizador=datos.organizador
    )
    log.info(
        "INTERNO_REUNIONES op=cancelar reunion=%s organizador=%s ip=%s resultado=%s eliminados=%s copias=%s",
        datos.reunion_id,
        datos.organizador,
        ip,
        res["accion"],
        res["eliminados"],
        res["copias_invitados"],
    )
    return {"success": True, **res}
