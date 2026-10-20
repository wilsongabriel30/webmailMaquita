"""Zonas DNS del servidor (panel → Hospedaje → Zonas DNS).

El servidor es autoritativo de sus zonas (BIND). Aquí se ven y editan los registros; cada cambio lo
valida y aplica el ayudante maquita-dns (named-checkzone antes de recargar) y queda en auditoría.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_admin, require_superadmin
from app.dns.ayudante import auditar, ayudante, b64

router = APIRouter(prefix="/api/dns", tags=["dns"])
RE_ZONA = re.compile(r"^(?=.{4,200}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
RE_ID = re.compile(r"^[0-9a-f]{8}$")


def _zona(z: str) -> str:
    z = (z or "").strip().lower().rstrip(".")
    if not RE_ZONA.match(z):
        raise HTTPException(400, "Zona no válida")
    return z


@router.get("")
async def estado(admin: dict = Depends(get_current_admin)):
    datos = await ayudante("dns", "estado")
    datos["lista"] = (await ayudante("dns", "listar"))["zonas"]
    return datos


class Servidor(BaseModel):
    ip_correo: str
    ip_web: str | None = None
    ns: list[dict]


@router.put("/servidor")
async def servidor(body: Servidor, r: Request, admin: dict = Depends(require_superadmin)):
    res = await ayudante("dns", "servidor", b64(body.model_dump()))
    await auditar(r, admin, "dns_servidor", "servidor", {"ip_correo": body.ip_correo, "ns": len(body.ns)})
    return res


@router.get("/certificado/estado")
async def certificado_estado(admin: dict = Depends(get_current_admin)):
    """Certificado del correo: nombres que cubre, vencimiento y si los servicios ya lo usan."""
    return await ayudante("dns", "certificado-estado")


@router.post("/certificado")
async def certificado_emitir(r: Request, admin: dict = Depends(require_superadmin)):
    """Emite o amplía el certificado del correo para todos los dominios que ya apuntan aquí."""
    res = await ayudante("dns", "certificado-correo", tiempo=600)
    await auditar(r, admin, "dns_certificado_correo", res.get("linaje", ""), {"incluidos": res.get("incluidos")})
    return res


@router.get("/{zona}")
async def ver(zona: str, admin: dict = Depends(get_current_admin)):
    return await ayudante("dns", "ver", _zona(zona))


@router.get("/{zona}/comprobar")
async def comprobar(zona: str, admin: dict = Depends(get_current_admin)):
    return await ayudante("dns", "comprobar", _zona(zona), tiempo=120)


class Registro(BaseModel):
    nombre: str = "@"
    tipo: str
    valor: str
    ttl: int = 3600
    prioridad: int | None = None


@router.post("/{zona}/registros", status_code=201)
async def agregar(zona: str, body: Registro, r: Request, admin: dict = Depends(require_superadmin)):
    zona = _zona(zona)
    res = await ayudante("dns", "agregar", zona, b64(body.model_dump()))
    await auditar(r, admin, "dns_registro_agregar", zona, body.model_dump())
    return res


@router.put("/{zona}/registros/{reg_id}")
async def modificar(zona: str, reg_id: str, body: Registro, r: Request, admin: dict = Depends(require_superadmin)):
    zona = _zona(zona)
    if not RE_ID.match(reg_id):
        raise HTTPException(400, "Registro no válido")
    res = await ayudante("dns", "modificar", zona, reg_id, b64(body.model_dump()))
    await auditar(r, admin, "dns_registro_modificar", zona, dict(body.model_dump(), id=reg_id))
    return res


@router.delete("/{zona}/registros/{reg_id}")
async def borrar_registro(zona: str, reg_id: str, r: Request, admin: dict = Depends(require_superadmin)):
    zona = _zona(zona)
    if not RE_ID.match(reg_id):
        raise HTTPException(400, "Registro no válido")
    res = await ayudante("dns", "borrar-registro", zona, reg_id)
    await auditar(r, admin, "dns_registro_borrar", zona, {"id": reg_id})
    return res


class Confirmacion(BaseModel):
    confirmacion: str


@router.delete("/{zona}")
async def borrar(zona: str, body: Confirmacion, r: Request, admin: dict = Depends(require_superadmin)):
    zona = _zona(zona)
    if (body.confirmacion or "").strip().lower() != zona:
        raise HTTPException(400, "Escriba la zona exacta para confirmar")
    res = await ayudante("dns", "borrar", zona, zona)
    await auditar(r, admin, "dns_zona_borrar", zona)
    return res
