"""Subdominios y dominios alias de los sitios, con su registro DNS.

Un sitio puede ser un dominio, un subdominio (blog.ejemplo.org) o tener alias (otros dominios que muestran
el mismo sitio). Si el nombre pertenece a una zona que administra este servidor («Zonas DNS»), el registro
A se crea solo; si no, se devuelve la IP a la que hay que apuntarlo en el proveedor del dominio.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import require_superadmin
from app.dns.ayudante import ayudante, b64
from app.sitios.router import _auditar, _ayudante, _dominio

router = APIRouter(prefix="/api/sitios", tags=["sitios"])


async def registrar_dns(dominios: list[str], con_www: bool) -> list[dict]:
    """Crea los registros A que falten en las zonas propias. Nunca impide crear el sitio: informa."""
    if not dominios:
        return []
    try:
        zonas = [z["zona"] for z in (await ayudante("dns", "listar"))["zonas"]]
        srv = await ayudante("dns", "servidor-ver")
    except HTTPException:
        zonas, srv = [], {}
    ip = srv.get("ip_web") or srv.get("ip_correo")
    resultado = []
    for dominio in dominios:
        zona = max((z for z in zonas if dominio == z or dominio.endswith("." + z)), key=len, default=None)
        nombres = [dominio] + ([f"www.{dominio}"] if con_www else [])
        if not zona or not ip:
            resultado += [{"nombre": n, "estado": "externo", "ip": ip} for n in nombres]
            continue
        try:
            existentes = {(r["nombre"], r["tipo"]) for r in (await ayudante("dns", "ver", zona))["registros"]}
        except HTTPException as e:
            resultado += [{"nombre": n, "estado": "error", "detalle": e.detail} for n in nombres]
            continue
        for nombre in nombres:
            relativo = "@" if nombre == zona else nombre[: -len(zona) - 1]
            if (relativo, "A") in existentes or (relativo, "CNAME") in existentes:
                resultado.append({"nombre": nombre, "estado": "ya estaba", "zona": zona})
                continue
            try:
                await ayudante("dns", "agregar", zona, b64({"nombre": relativo, "tipo": "A", "valor": ip}))
                resultado.append({"nombre": nombre, "estado": "creado", "zona": zona, "ip": ip})
            except HTTPException as e:
                resultado.append({"nombre": nombre, "estado": "error", "detalle": e.detail})
    return resultado


async def quitar_dns(dominios: list[str], con_www: bool) -> list[str]:
    """Al dar de baja un sitio: borra los registros A que el panel creó para él en las zonas propias (no los
    del sistema de la zona, como «@» y «www» del dominio principal, ni los que apuntan a otro servidor)."""
    try:
        zonas = [z["zona"] for z in (await ayudante("dns", "listar"))["zonas"]]
        srv = await ayudante("dns", "servidor-ver")
    except HTTPException:
        return []
    ip = srv.get("ip_web") or srv.get("ip_correo")
    borrados = []
    for dominio in dominios:
        zona = max((z for z in zonas if dominio == z or dominio.endswith("." + z)), key=len, default=None)
        if not zona or not ip:
            continue
        nombres = {("@" if n == zona else n[: -len(zona) - 1]) for n in [dominio] + ([f"www.{dominio}"] if con_www else [])}
        try:
            registros = (await ayudante("dns", "ver", zona))["registros"]
            for reg in registros:
                if reg["nombre"] in nombres and reg["tipo"] == "A" and reg["valor"] == ip and not reg.get("sistema"):
                    await ayudante("dns", "borrar-registro", zona, reg["id"])
                    borrados.append(f"{reg['nombre']}.{zona}")
        except HTTPException:
            continue  # la baja del sitio no depende del DNS
    return borrados


class Alias(BaseModel):
    alias: list[str]


@router.put("/{dominio}/alias")
async def cambiar_alias(dominio: str, body: Alias, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    if len(body.alias) > 10:
        raise HTTPException(400, "Se admiten hasta 10 dominios alias")
    lista = sorted({_dominio(a) for a in body.alias if a.strip()})
    res = await _ayudante("alias", dominio, b64(lista), tiempo=900)
    res["dns"] = await registrar_dns(lista, res.get("www", True))
    await _auditar(r, admin, "sitio_alias", dominio, {"alias": lista})
    return res
