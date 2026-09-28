"""Marca de cada empresa: nombre, lema, datos de contacto, color, logo e icono.

Es lo que ve su gente en la pantalla de entrada del correo. Lo que una empresa no defina se
hereda de la marca general del servidor. Los nombres de servidor (mail.<empresa>) se muestran
pero no se cambian desde aquí: publicar uno exige DNS, certificado y nginx.
"""

import os
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from app import config_extra
from app.imagenes import FORMATOS, formato_de, medidas
from app.sesion import admin_actual, auditar
from app.validacion import texto_limpio

router = APIRouter(prefix="/api/marca", tags=["marca"])

CLAVES = ("org_name", "org_slogan", "org_email", "org_website", "org_phone", "primary_color", "footer_text")
TIPOS = ("logo", "favicon")
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_WEB = re.compile(r"^https?://[^\s<>\"']{3,300}$")
_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp", ".ico": "image/x-icon"}


def _dominio(admin: dict, dominio: str) -> str:
    dominio = str(dominio or "").strip().lower()
    if dominio not in admin["dominios"]:
        raise HTTPException(404, "No encontrado")
    return dominio


def _carpeta(dominio: str, tipo: str) -> str:
    # `dominio` viene de la lista de dominios asignados, nunca de la petición tal cual.
    return os.path.join(config_extra.DIR_MARCA, dominio, tipo)


def _archivo(dominio: str, tipo: str) -> str | None:
    carpeta = _carpeta(dominio, tipo)
    if not os.path.isdir(carpeta):
        return None
    nombres = sorted(n for n in os.listdir(carpeta) if os.path.splitext(n)[1] in _MIME)
    return os.path.join(carpeta, nombres[0]) if nombres else None


@router.get("")
async def ver(request: Request, admin: dict = Depends(admin_actual)):
    db = request.app.state.db
    textos = await db.fetch(
        "SELECT dominio, clave, valor FROM branding_empresa WHERE dominio = ANY($1::text[])", admin["dominios"])
    hosts = await db.fetch(
        "SELECT host, dominio, activo FROM portal_empresa WHERE dominio = ANY($1::text[]) ORDER BY host", admin["dominios"])
    salida = {d: {"dominio": d, "marca": {}, "portales": [], "logo": False, "favicon": False} for d in admin["dominios"]}
    for t in textos:
        if t["clave"] in CLAVES and t["valor"]:
            salida[t["dominio"]]["marca"][t["clave"]] = t["valor"]
    for h in hosts:
        salida[h["dominio"]]["portales"].append({"host": h["host"], "activo": h["activo"]})
    for d in salida:
        for tipo in TIPOS:
            salida[d][tipo] = _archivo(d, tipo) is not None
    return {"empresas": list(salida.values()), "max_kb": config_extra.MARCA_MAX_BYTES // 1024}


@router.put("/{dominio}")
async def guardar(dominio: str, request: Request, admin: dict = Depends(admin_actual)):
    """Un valor vacío borra la clave: vuelve a heredarse de la marca general."""
    dominio = _dominio(admin, dominio)
    datos = await request.json()
    cambios = {}
    for clave in CLAVES:
        if clave not in datos:
            continue
        valor = texto_limpio(datos[clave], 500)
        if valor and clave == "primary_color" and not _COLOR.match(valor):
            raise HTTPException(400, "El color debe ir en formato #RRGGBB")
        if valor and clave == "org_website" and not _WEB.match(valor):
            raise HTTPException(400, "La página web debe empezar por http:// o https://")
        if valor and clave == "org_email" and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", valor):
            raise HTTPException(400, "El correo de contacto no es válido")
        cambios[clave] = valor
    db = request.app.state.db
    async with db.acquire() as con, con.transaction():
        for clave, valor in cambios.items():
            if valor:
                await con.execute(
                    """INSERT INTO branding_empresa (dominio, clave, valor) VALUES ($1, $2, $3)
                       ON CONFLICT (dominio, clave) DO UPDATE SET valor = EXCLUDED.valor""",
                    dominio, clave, valor)
            else:
                await con.execute("DELETE FROM branding_empresa WHERE dominio = $1 AND clave = $2", dominio, clave)
    await auditar(request, admin, "marca_editar", dominio, cambios)
    return {"ok": True}


@router.put("/{dominio}/archivo/{tipo}")
async def subir(dominio: str, tipo: str, request: Request, admin: dict = Depends(admin_actual)):
    """El cuerpo de la petición es la imagen tal cual."""
    dominio = _dominio(admin, dominio)
    if tipo not in TIPOS:
        raise HTTPException(404, "No encontrado")
    datos = await request.body()
    if not datos:
        raise HTTPException(400, "No llegó ninguna imagen")
    if len(datos) > config_extra.MARCA_MAX_BYTES:
        raise HTTPException(400, f"La imagen pesa demasiado (máximo {config_extra.MARCA_MAX_BYTES // 1024} KB). Una imagen ligera carga mejor en conexiones lentas.")
    formato = formato_de(datos)
    if formato is None or (formato == "ico" and tipo != "favicon"):
        raise HTTPException(400, "Formato no admitido. Usa PNG, JPG o WebP" + (" (o ICO para el icono)." if tipo == "favicon" else "."))
    tamano = medidas(datos, formato)
    if tamano and (max(tamano) > 2000 or min(tamano) < 16):
        raise HTTPException(400, "La imagen debe medir entre 16 y 2000 píxeles por lado")

    carpeta = _carpeta(dominio, tipo)
    try:
        # Las carpetas heredan el grupo compartido de la carpeta madre (bit setgid) y salen con
        # permisos 775 por el UMask del servicio. No se les hace chmod: el confinamiento
        # (RestrictSUIDSGID) prohíbe a este proceso poner bits setgid, y está bien que así sea.
        os.makedirs(carpeta, exist_ok=True)
        for viejo in os.listdir(carpeta):
            os.remove(os.path.join(carpeta, viejo))
        destino = os.path.join(carpeta, tipo + FORMATOS[formato])
        with open(destino, "wb") as f:
            f.write(datos)
        os.chmod(destino, 0o664)  # el webmail (otro usuario) tiene que poder leerlo
    except OSError:
        raise HTTPException(500, "No se pudo guardar la imagen. Avisa al administrador general.")
    await auditar(request, admin, "marca_archivo", dominio, {"tipo": tipo, "formato": formato, "bytes": len(datos)})
    return {"ok": True}


@router.delete("/{dominio}/archivo/{tipo}")
async def quitar(dominio: str, tipo: str, request: Request, admin: dict = Depends(admin_actual)):
    dominio = _dominio(admin, dominio)
    if tipo not in TIPOS:
        raise HTTPException(404, "No encontrado")
    ruta = _archivo(dominio, tipo)
    if ruta:
        try:
            os.remove(ruta)
        except OSError:
            raise HTTPException(500, "No se pudo quitar la imagen. Avisa al administrador general.")
    await auditar(request, admin, "marca_archivo_quitar", dominio, {"tipo": tipo})
    return {"ok": True}


@router.get("/{dominio}/archivo/{tipo}")
async def descargar(dominio: str, tipo: str, admin: dict = Depends(admin_actual)):
    dominio = _dominio(admin, dominio)
    ruta = _archivo(dominio, tipo) if tipo in TIPOS else None
    if not ruta:
        raise HTTPException(404, "No encontrado")
    with open(ruta, "rb") as f:
        datos = f.read(config_extra.MARCA_MAX_BYTES * 8)
    return Response(datos, media_type=_MIME[os.path.splitext(ruta)[1]], headers={"X-Content-Type-Options": "nosniff"})
