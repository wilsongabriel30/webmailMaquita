"""Alertas de anomalías: listar, reconocer y cerrar (escalamiento sencillo).

  abierta     la creó el recolector; si es alta y nadie la reconoce en `escalar_tras_horas`, se avisa
              otra vez como ESCALADA.
  reconocida  alguien la está mirando (queda quién y cuándo); ya no escala.
  cerrada     resuelta o falso positivo, con nota. Se conserva `retencion_dias` días.
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth.dependencies import require_operador
from app.dns.ayudante import auditar

from . import consultas

router = APIRouter(prefix="/api/seguridad/alertas", tags=["seguridad"])


def _db(r: Request):
    return r.app.state.db


@router.get("")
async def listar(r: Request, estado: Literal["abierta", "reconocida", "cerrada", "pendientes"] | None = None,
                 severidad: Literal["baja", "media", "alta"] | None = None, limite: int = 200,
                 admin: dict = Depends(require_operador)):
    return await consultas.alertas(_db(r), estado, severidad, max(1, min(limite, 1000)))


class Reconocer(BaseModel):
    nota: str = Field("", max_length=2000)


class Cerrar(BaseModel):
    resolucion: Literal["resuelta", "falso_positivo"]
    nota: str = Field("", max_length=2000)


@router.post("/{aid}/reconocer")
async def reconocer(aid: int, body: Reconocer, r: Request, admin: dict = Depends(require_operador)):
    fila = await _db(r).fetchrow(
        "UPDATE seg_alertas SET estado = 'reconocida', reconocida_por = $2, reconocida_en = now(), "
        "nota = COALESCE(NULLIF($3, ''), nota) WHERE id = $1 AND estado = 'abierta' RETURNING id, regla, cuenta, ip",
        aid, admin["username"], body.nota.strip())
    if not fila:
        raise HTTPException(409, "La alerta no existe o ya no está abierta")
    await auditar(r, admin, "seguridad_alerta_reconocer", f"alerta {aid}", {"regla": fila["regla"], "cuenta": fila["cuenta"], "ip": fila["ip"]})
    return {"ok": True}


@router.post("/{aid}/cerrar")
async def cerrar(aid: int, body: Cerrar, r: Request, admin: dict = Depends(require_operador)):
    nota = body.nota.strip()
    if body.resolucion == "falso_positivo" and not nota:
        raise HTTPException(400, "Indique en la nota por qué es un falso positivo")
    fila = await _db(r).fetchrow(
        "UPDATE seg_alertas SET estado = 'cerrada', resolucion = $2, cerrada_por = $3, cerrada_en = now(), "
        "reconocida_por = COALESCE(reconocida_por, $3), reconocida_en = COALESCE(reconocida_en, now()), "
        "nota = CASE WHEN $4 = '' THEN nota ELSE $4 END WHERE id = $1 AND estado <> 'cerrada' RETURNING id, regla, cuenta, ip",
        aid, body.resolucion, admin["username"], nota)
    if not fila:
        raise HTTPException(409, "La alerta no existe o ya está cerrada")
    await auditar(r, admin, "seguridad_alerta_cerrar", f"alerta {aid}",
                  {"regla": fila["regla"], "resolucion": body.resolucion, "cuenta": fila["cuenta"], "ip": fila["ip"]})
    return {"ok": True}
