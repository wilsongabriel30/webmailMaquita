"""Administrador de archivos del sitio: listar, subir, descargar, crear carpeta, renombrar o mover, copiar, borrar
(a la papelera del sitio), comprimir en .zip, descomprimir y cambiar permisos.

Todo ocurre dentro de la carpeta pública del sitio y con su usuario de sistema, nunca como root: el ayudante
resuelve cada ruta con realpath, no sigue enlaces que salgan y descomprime con protección contra «zip slip»,
bombas y enlaces (deploy/sitios/lib/archivos*.py). Aquí se valida la forma y se registra en auditoría lo que
cambia algo.
"""

import os
import re
import secrets

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from app.auth.dependencies import require_superadmin
from app.dns.ayudante import b64
from app.sitios.entrega import enlace
from app.sitios.router import _auditar, _ayudante, _dominio

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
SUBIDAS = "/var/lib/maquita-sitios/subidas"
TOPE_SUBIDA = 512 * 1048576
MODOS = ("644", "755", "600", "700", "640", "750")
RE_PAPELERA = re.compile(r"^[0-9a-f]{12}$")
LARGO = 1800  # segundos para copiar, comprimir o descomprimir carpetas grandes


def _ruta(valor: str) -> str:
    """Ruta relativa a la carpeta pública, en base64url para el ayudante («.» = la raíz)."""
    valor = (valor or "").strip()
    valor = valor.lstrip("/") or "."
    if len(valor) > 1000 or re.search(r"[\x00-\x1f\x7f]", valor) or ".." in valor.split("/"):
        raise HTTPException(400, "Ruta no válida")
    return b64(valor)


def _unir(carpeta: str, nombre: str) -> str:
    nombre = os.path.basename((nombre or "").replace("\\", "/")).strip()
    if not nombre or nombre in (".", "..") or len(nombre.encode()) > 255 or re.search(r"[\x00-\x1f\x7f]", nombre):
        raise HTTPException(400, "Nombre de archivo no válido")
    carpeta = (carpeta or "").strip().strip("/")
    return f"{carpeta}/{nombre}" if carpeta and carpeta != "." else nombre


@router.get("/{dominio}/archivos")
async def listar(dominio: str, ruta: str = ".", admin: dict = Depends(require_superadmin)):
    return await _ayudante("archivos-listar", _dominio(dominio), _ruta(ruta))


@router.post("/{dominio}/archivos/subir")
async def subir(dominio: str, r: Request, archivo: UploadFile = File(...), carpeta: str = Form("."),
                reemplazar: bool = Form(False), admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    destino = _unir(carpeta, archivo.filename or "")
    ruta = _ruta(destino)
    if not os.path.isdir(SUBIDAS):
        raise HTTPException(503, "Falta la carpeta de subidas: actualice la sección de sitios (instalar-app.sh sitios)")
    nombre = secrets.token_hex(16) + ".subida"
    total = 0
    try:
        with open(os.path.join(SUBIDAS, nombre), "xb") as f:
            os.chmod(f.name, 0o640)
            while bloque := await archivo.read(1 << 20):
                total += len(bloque)
                if total > TOPE_SUBIDA:
                    raise HTTPException(413, "El archivo supera 512 MB: súbalo por SFTP")
                f.write(bloque)
    except BaseException:
        if os.path.exists(os.path.join(SUBIDAS, nombre)):
            os.remove(os.path.join(SUBIDAS, nombre))
        raise
    args = ["archivos-subir", dominio, ruta, nombre] + (["reemplazar"] if reemplazar else [])
    res = await _ayudante(*args, tiempo=LARGO)  # el ayudante borra la subida, salga bien o no
    await _auditar(r, admin, "sitio_archivo_subir", dominio, {"ruta": destino, "bytes": total, "reemplazar": reemplazar})
    return res


class Ruta(BaseModel):
    ruta: str


class Par(BaseModel):
    origen: str
    destino: str


class Comprimir(BaseModel):
    rutas: list[str]
    destino: str


class Permisos(BaseModel):
    ruta: str
    modo: str


@router.post("/{dominio}/archivos/descargar")
async def descargar(dominio: str, body: Ruta, admin: dict = Depends(require_superadmin)):
    res = await _ayudante("archivos-descargar", _dominio(dominio), _ruta(body.ruta), tiempo=LARGO)
    return {"enlace": enlace(res.get("archivo", ""), res.get("nombre") or "descarga"), "bytes": res.get("bytes")}


@router.post("/{dominio}/archivos/carpeta")
async def carpeta(dominio: str, body: Ruta, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    res = await _ayudante("archivos-carpeta", dominio, _ruta(body.ruta))
    await _auditar(r, admin, "sitio_archivo_carpeta", dominio, {"ruta": body.ruta})
    return res


@router.post("/{dominio}/archivos/{accion}")
async def mover_o_copiar(dominio: str, accion: str, body: Par, r: Request, admin: dict = Depends(require_superadmin)):
    if accion not in ("mover", "copiar", "descomprimir"):
        raise HTTPException(404, "Acción no válida")
    dominio = _dominio(dominio)
    res = await _ayudante(f"archivos-{accion}", dominio, _ruta(body.origen), _ruta(body.destino), tiempo=LARGO)
    await _auditar(r, admin, f"sitio_archivo_{accion}", dominio, {"origen": body.origen, "destino": body.destino})
    return res


@router.post("/{dominio}/archivos-borrar")
async def borrar(dominio: str, body: Ruta, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    res = await _ayudante("archivos-borrar", dominio, _ruta(body.ruta), tiempo=LARGO)
    await _auditar(r, admin, "sitio_archivo_borrar", dominio, {"ruta": body.ruta})
    return res


@router.post("/{dominio}/archivos-comprimir")
async def comprimir(dominio: str, body: Comprimir, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    if not 1 <= len(body.rutas) <= 500:
        raise HTTPException(400, "Elija entre 1 y 500 elementos")
    for ruta in body.rutas + [body.destino]:
        _ruta(ruta)
    datos = b64({"rutas": [ruta.strip().lstrip("/") or "." for ruta in body.rutas], "destino": body.destino.strip().lstrip("/")})
    if len(datos) > 40000:
        raise HTTPException(400, "Demasiados elementos: comprímalos por partes")
    res = await _ayudante("archivos-comprimir", dominio, datos, tiempo=LARGO)
    await _auditar(r, admin, "sitio_archivo_comprimir", dominio, {"destino": body.destino, "elementos": len(body.rutas)})
    return res


@router.post("/{dominio}/archivos-permisos")
async def permisos(dominio: str, body: Permisos, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    if body.modo not in MODOS:
        raise HTTPException(400, "Permisos no admitidos (644, 755, 600, 700, 640 o 750)")
    res = await _ayudante("archivos-permisos", dominio, _ruta(body.ruta), body.modo)
    await _auditar(r, admin, "sitio_archivo_permisos", dominio, {"ruta": body.ruta, "modo": body.modo})
    return res


@router.get("/{dominio}/archivos-papelera")
async def papelera(dominio: str, admin: dict = Depends(require_superadmin)):
    return await _ayudante("archivos-papelera", _dominio(dominio))


@router.post("/{dominio}/archivos-papelera/{elemento}/recuperar")
async def recuperar(dominio: str, elemento: str, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    if not RE_PAPELERA.match(elemento):
        raise HTTPException(400, "Elemento no válido")
    res = await _ayudante("archivos-recuperar", dominio, elemento)
    await _auditar(r, admin, "sitio_archivo_recuperar", dominio, {"ruta": res.get("ruta")})
    return res


@router.delete("/{dominio}/archivos-papelera")
async def vaciar(dominio: str, r: Request, admin: dict = Depends(require_superadmin)):
    dominio = _dominio(dominio)
    res = await _ayudante("archivos-vaciar", dominio, tiempo=LARGO)
    await _auditar(r, admin, "sitio_archivo_vaciar_papelera", dominio, res)
    return res
