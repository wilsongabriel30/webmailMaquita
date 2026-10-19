"""Trabajos de cron de los sitios: listar, guardar la lista, ejecutar ahora y ver la salida.

Las órdenes corren con el usuario del sitio y encerradas (ver deploy/sitios/lib/tareas.py). Aquí se valida la
forma y se registra en auditoría.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_superadmin
from app.dns.ayudante import b64
from app.sitios.router import _auditar, _ayudante, _dominio

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
RE_ID = re.compile(r"^[0-9a-f]{8}$")


class Trabajo(BaseModel):
    id: str | None = None
    horario: str
    orden: str
    descripcion: str = ""
    activo: bool = True


class Trabajos(BaseModel):
    trabajos: list[Trabajo]


def _id(valor: str) -> str:
    if not RE_ID.match(valor or ""):
        raise HTTPException(400, "Trabajo no válido")
    return valor


@router.get("/{dominio}/tareas")
async def listar(dominio: str, admin: dict = Depends(get_current_admin)):
    return await _ayudante("tareas", _dominio(dominio))


@router.put("/{dominio}/tareas")
async def guardar(dominio: str, body: Trabajos, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    if len(body.trabajos) > 20:
        raise HTTPException(400, "Se admiten hasta 20 trabajos por sitio")
    datos = [t.model_dump() for t in body.trabajos]
    texto = b64(datos)
    if len(texto) > 40000:
        raise HTTPException(400, "Demasiados datos")
    res = await _ayudante("tareas-guardar", dominio, texto, tiempo=120)
    await _auditar(r, admin, "sitio_cron_guardar", dominio,
                   {"trabajos": [{"horario": t["horario"], "orden": t["orden"][:200], "activo": t["activo"]} for t in datos]})
    return res


@router.post("/{dominio}/tareas/{tarea}/ejecutar")
async def ejecutar(dominio: str, tarea: str, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    res = await _ayudante("tarea-ejecutar", dominio, _id(tarea))
    await _auditar(r, admin, "sitio_cron_ejecutar", dominio, {"id": tarea})
    return res


@router.get("/{dominio}/tareas/{tarea}/registro")
async def registro(dominio: str, tarea: str, admin: dict = Depends(get_current_admin)):
    return await _ayudante("tarea-registro", _dominio(dominio), _id(tarea))
