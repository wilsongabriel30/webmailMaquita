"""Zona DNS del dominio, cuando la sirve este servidor (maquita-dns).

Solo la zona de un dominio asignado exacto. Los registros del correo (MX, SPF, DKIM, DMARC,
MTA-STS, TLSA…) y los NS/SOA llegan marcados como «protegidos»: se ven, pero el intermediario
rechaza tocarlos (403), porque un error en ellos deja sin correo a todo el dominio.
"""

from fastapi import APIRouter, Depends, Request

from app.sesion import admin_actual
from app.sitios import validacion as v
from app.sitios.comun import cuerpo, exigir_dominio, llamar

router = APIRouter(prefix="/api/sitios/dns", tags=["sitios"])


def _resumen(registro: dict) -> dict:
    return {k: registro[k] for k in ("nombre", "tipo", "valor", "ttl", "prioridad")}


@router.get("/{dominio}")
async def ver(dominio: str, request: Request, admin: dict = Depends(admin_actual)):
    return await llamar(request, admin, "dns-ver", exigir_dominio(admin, dominio))


@router.post("/{dominio}", status_code=201)
async def agregar(dominio: str, request: Request, admin: dict = Depends(admin_actual)):
    dominio = exigir_dominio(admin, dominio)
    registro = v.registro_dns((await cuerpo(request)).get("registro"))
    return await llamar(request, admin, "dns-agregar", dominio, {"registro": registro}, "dns_agregar", _resumen(registro))


@router.put("/{dominio}/{registro_id}")
async def modificar(dominio: str, registro_id: str, request: Request, admin: dict = Depends(admin_actual)):
    dominio = exigir_dominio(admin, dominio)
    registro_id = v.con_forma(v.RE_REGISTRO, registro_id, "Registro no válido")
    registro = v.registro_dns((await cuerpo(request)).get("registro"))
    return await llamar(request, admin, "dns-modificar", dominio, {"id": registro_id, "registro": registro},
                        "dns_modificar", {"id": registro_id, **_resumen(registro)})


@router.delete("/{dominio}/{registro_id}")
async def borrar(dominio: str, registro_id: str, request: Request, admin: dict = Depends(admin_actual)):
    dominio = exigir_dominio(admin, dominio)
    registro_id = v.con_forma(v.RE_REGISTRO, registro_id, "Registro no válido")
    return await llamar(request, admin, "dns-borrar", dominio, {"id": registro_id}, "dns_borrar", {"id": registro_id})
