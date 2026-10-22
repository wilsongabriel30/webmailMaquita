"""DNS dinámico de la zona de un dominio asignado (v1.11): una ficha por nombre (casa.tu-dominio), con su usuario y
su contraseña propios para el router o el programa que actualiza la IP (dyndns2: /nic/update).

La contraseña vuelve UNA vez, al crear la ficha o al pedir otra: ni se audita ni se guarda aquí (el intermediario
guarda solo su hash).
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Request

from app.sesion import admin_actual
from app.sitios.comun import cuerpo, exigir_dominio, llamar

router = APIRouter(prefix="/api/sitios/dns", tags=["sitios"])
RE_FICHA = re.compile(r"[0-9a-f]{8}")
RE_NOMBRE = re.compile(r"[a-z0-9.-]{1,200}")


def _ficha(valor: str) -> str:
    if not RE_FICHA.fullmatch(valor or ""):
        raise HTTPException(400, "Ficha no válida")
    return valor


@router.get("/{dominio}/dinamico")
async def ver(dominio: str, request: Request, admin: dict = Depends(admin_actual)):
    return await llamar(request, admin, "ddns-ver", exigir_dominio(admin, dominio))


@router.post("/{dominio}/dinamico", status_code=201)
async def crear(dominio: str, request: Request, admin: dict = Depends(admin_actual)):
    dominio = exigir_dominio(admin, dominio)
    nombre = str((await cuerpo(request)).get("nombre") or "").strip().lower()
    if not RE_NOMBRE.fullmatch(nombre):
        raise HTTPException(400, "Nombre no válido")
    return await llamar(request, admin, "ddns-crear", dominio, {"nombre": nombre}, "dns_dinamico_crear", {"nombre": nombre})


@router.post("/{dominio}/dinamico/{ficha}/clave")
async def clave(dominio: str, ficha: str, request: Request, admin: dict = Depends(admin_actual)):
    dominio = exigir_dominio(admin, dominio)
    ficha = _ficha(ficha)
    return await llamar(request, admin, "ddns-clave", dominio, {"id": ficha}, "dns_dinamico_clave", {"id": ficha})


@router.delete("/{dominio}/dinamico/{ficha}")
async def borrar(dominio: str, ficha: str, request: Request, admin: dict = Depends(admin_actual)):
    dominio = exigir_dominio(admin, dominio)
    ficha = _ficha(ficha)
    return await llamar(request, admin, "ddns-borrar", dominio, {"id": ficha}, "dns_dinamico_borrar", {"id": ficha})
