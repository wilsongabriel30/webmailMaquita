"""Aplicaciones propias de los sitios (estáticas, Python y Node.js): alta, estado, acciones, variables
de entorno y retirada. Todo lo hace el ayudante maquita-sitios por maquita-sudo; aquí se valida la
forma de la entrada y se registra en auditoría (sin los valores de las variables)."""

import base64
import json
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_superadmin
from app.sitios.router import _auditar, _ayudante, _dominio

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
RE_VARIABLE = re.compile(r"^[A-Z_][A-Z0-9_]{0,63}$")


def _b64(datos) -> str:
    texto = base64.urlsafe_b64encode(json.dumps(datos, ensure_ascii=False).encode()).decode().rstrip("=")
    if len(texto) > 8000:
        raise HTTPException(400, "Datos demasiado largos")
    return texto


class NuevaPropia(BaseModel):
    tipo: str  # estatico | python | node
    git: str | None = None
    rama: str | None = None
    carpeta: str | None = None
    spa: bool = False
    modo: str | None = None  # wsgi | asgi
    entrada: str | None = None
    puerto_publico: int | None = None
    protocolo: str | None = None


@router.post("/{dominio}/propia", status_code=201)
async def crear(dominio: str, body: NuevaPropia, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    if body.tipo not in ("estatico", "python", "node"):
        raise HTTPException(400, "Tipo de aplicación no válido")
    conf = {k: v for k, v in body.model_dump().items() if k != "tipo" and v not in (None, "")}
    res = await _ayudante("propia-crear", dominio, body.tipo, _b64(conf), tiempo=1100)
    await _auditar(
        r,
        admin,
        "sitio_propia_crear",
        dominio,
        {"tipo": body.tipo, "git": body.git, "puerto_publico": body.puerto_publico},
    )
    return res


@router.get("/{dominio}/propia")
async def estado(dominio: str, admin: dict = Depends(get_current_admin)):
    return await _ayudante("propia-estado", _dominio(dominio))


class Accion(BaseModel):
    accion: str  # iniciar | detener | reiniciar | desplegar


@router.post("/{dominio}/propia/accion")
async def accion(dominio: str, body: Accion, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    if body.accion not in ("iniciar", "detener", "reiniciar", "desplegar"):
        raise HTTPException(400, "Acción no válida")
    res = await _ayudante("propia-accion", dominio, body.accion, tiempo=1100)
    await _auditar(r, admin, f"sitio_propia_{body.accion}", dominio)
    return res


class Variables(BaseModel):
    # {"CLAVE": "valor"} pone o cambia; {"CLAVE": null} conserva el valor guardado; las ausentes se quitan.
    variables: dict[str, str | None]


@router.put("/{dominio}/propia/entorno")
async def entorno(dominio: str, body: Variables, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    if len(body.variables) > 50 or any(not RE_VARIABLE.match(k) for k in body.variables):
        raise HTTPException(400, "Nombres de variable: mayúsculas, números y _ (máximo 50 variables)")
    res = await _ayudante("propia-entorno", dominio, _b64(body.variables), tiempo=120)
    await _auditar(r, admin, "sitio_propia_entorno", dominio, {"variables": sorted(body.variables)})
    return res


class Confirmacion(BaseModel):
    confirmacion: str


@router.delete("/{dominio}/propia")
async def quitar(dominio: str, body: Confirmacion, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    if (body.confirmacion or "").strip().lower() != dominio:
        raise HTTPException(400, "Escriba el dominio para confirmar")
    res = await _ayudante("propia-quitar", dominio, dominio, tiempo=120)
    await _auditar(r, admin, "sitio_propia_quitar", dominio)
    return res
