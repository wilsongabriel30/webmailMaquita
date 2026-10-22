"""Usuarios adicionales de las bases del sitio (v1.11): permisos a medida, clave nueva y acceso remoto con TLS.

El nombre lo pone el servidor («u_<sitio>_<sufijo>»): aquí solo se elige el sufijo. La contraseña la genera el
servidor y vuelve una sola vez; no se guarda en el portal ni en la auditoría. El acceso remoto desde el portal admite
redes de /16 (IPv4) o /48 (IPv6) como mucho: una más amplia solo la autoriza el administrador general.
"""

import ipaddress
import re

from fastapi import APIRouter, Depends, HTTPException, Request

from app.sesion import admin_actual
from app.sitios import validacion as v
from app.sitios.comun import cuerpo, exigir_sitio, llamar

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
RE_SUFIJO = re.compile(r"[a-z][a-z0-9]{1,9}")
RE_USUARIO = re.compile(r"u_[a-z0-9]+_[a-z][a-z0-9]{1,9}")
RE_PRIVILEGIO = re.compile(r"[A-Z][A-Z ]{2,30}")
PERFILES = ("lectura", "escritura", "estructura", "todo", "medida")


def _usuario(valor) -> str:
    valor = str(valor or "")
    if not RE_USUARIO.fullmatch(valor):
        raise HTTPException(400, "Usuario no válido")
    return valor


def _permisos(valor) -> dict:
    if not isinstance(valor, dict) or valor.get("perfil") not in PERFILES:
        raise HTTPException(400, "Elige los permisos: lectura, escritura, estructura, todo o a medida")
    if valor["perfil"] != "medida":
        return {"perfil": valor["perfil"]}
    lista = valor.get("lista")
    if not isinstance(lista, list) or not 1 <= len(lista) <= 20 or \
            not all(isinstance(p, str) and RE_PRIVILEGIO.fullmatch(p) for p in lista):
        raise HTTPException(400, "Elige al menos un permiso de la lista")
    return {"perfil": "medida", "lista": lista}


def _redes(valor) -> list[str]:
    if not isinstance(valor, list) or len(valor) > 20:
        raise HTTPException(400, "Se admiten hasta 20 IP o redes por usuario")
    salida = []
    for texto in valor:
        texto = str(texto or "").strip()
        if not texto:
            continue
        try:
            red = ipaddress.ip_network(texto, strict=False)
        except ValueError:
            raise HTTPException(400, f"IP o red no válida: {texto[:50]}")
        tope = 16 if red.version == 4 else 48
        if red.prefixlen < tope:
            raise HTTPException(400, f"Red demasiado amplia: {red}. Usa una de /{tope} o menor; una más amplia solo "
                                     "la puede autorizar el administrador general")
        salida.append(str(red))
    return salida


@router.get("/{sitio}/bases/usuarios")
async def listar(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "bases-usuarios", sitio)


@router.post("/{sitio}/bases/usuarios", status_code=201)
async def crear(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    datos = await cuerpo(request)
    base = v.con_forma(v.RE_BASE, datos.get("base"), "Base de datos no válida")
    sufijo = str(datos.get("sufijo") or "").strip()
    if not RE_SUFIJO.fullmatch(sufijo):
        raise HTTPException(400, "Nombre no válido: de 2 a 10 minúsculas o números, empezando por una letra")
    permisos = _permisos(datos.get("permisos"))
    return await llamar(request, admin, "base-usuario-crear", sitio, {"base": base, "sufijo": sufijo, "permisos": permisos},
                        "sitio_base_usuario_crear", {"base": base, "sufijo": sufijo, "permisos": permisos})


@router.put("/{sitio}/bases/usuarios/{usuario}/permisos")
async def permisos(sitio: str, usuario: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    usuario, nuevos = _usuario(usuario), _permisos((await cuerpo(request)).get("permisos"))
    return await llamar(request, admin, "base-usuario-permisos", sitio, {"usuario": usuario, "permisos": nuevos},
                        "sitio_base_usuario_permisos", {"usuario": usuario, "permisos": nuevos})


@router.post("/{sitio}/bases/usuarios/{usuario}/clave")
async def nueva_clave(sitio: str, usuario: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    usuario = _usuario(usuario)
    return await llamar(request, admin, "base-usuario-clave", sitio, {"usuario": usuario},
                        "sitio_base_usuario_clave", {"usuario": usuario})


@router.put("/{sitio}/bases/usuarios/{usuario}/remoto")
async def remoto(sitio: str, usuario: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    usuario, redes = _usuario(usuario), _redes((await cuerpo(request)).get("redes"))
    return await llamar(request, admin, "base-usuario-remoto", sitio, {"usuario": usuario, "redes": redes},
                        "sitio_base_usuario_remoto", {"usuario": usuario, "redes": redes})


@router.delete("/{sitio}/bases/usuarios/{usuario}")
async def borrar(sitio: str, usuario: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    usuario = _usuario(usuario)
    return await llamar(request, admin, "base-usuario-borrar", sitio, {"usuario": usuario},
                        "sitio_base_usuario_borrar", {"usuario": usuario})
