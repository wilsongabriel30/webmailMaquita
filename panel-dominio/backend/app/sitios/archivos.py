"""Administrador de archivos del sitio (v1.10): listar, subir, descargar, crear carpeta, renombrar o mover, copiar,
borrar (a la papelera del sitio, 30 días), comprimir en .zip, descomprimir y cambiar permisos.

Todo ocurre dentro de la carpeta pública y con el usuario de sistema del sitio, nunca como root (lo hace
maquita-sitios). Lo que sube viaja por la carpeta de subidas del portal, como los paquetes; lo que se descarga
vuelve por ella con un enlace de un solo uso (descargas.py). Subir, copiar, comprimir y descomprimir pasan por la
cuota de disco del dominio en el intermediario. En la auditoría queda cada cambio con su ruta.

No confundir con «Configuración» (avanzado.py): ese edita archivos de texto con versión anterior guardada.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Request

from app.sesion import admin_actual
from app.sitios import config, descargas, subidas
from app.sitios.comun import cuerpo, exigir_sitio, llamar

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
MODOS = ("644", "755", "600", "700", "640", "750")
RE_PAPELERA = re.compile(r"[0-9a-f]{12}")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _ruta(valor, raiz: bool = True) -> str:
    """Ruta relativa a la carpeta pública («.» = la raíz). El intermediario y maquita-sitios la encierran además."""
    valor = str(valor if valor is not None else "").strip().lstrip("/") or "."
    if len(valor) > 1000 or _CONTROL.search(valor) or "\\" in valor or ".." in valor.split("/") or (valor == "." and not raiz):
        raise HTTPException(400, "Ruta no válida")
    return valor


def _unir(carpeta: str, nombre: str) -> str:
    nombre = str(nombre or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not nombre or nombre in (".", "..") or len(nombre.encode()) > 255 or _CONTROL.search(nombre):
        raise HTTPException(400, "Nombre de archivo no válido")
    carpeta = _ruta(carpeta)
    return nombre if carpeta == "." else f"{carpeta.rstrip('/')}/{nombre}"


@router.get("/{sitio}/archivos")
async def listar(sitio: str, request: Request, ruta: str = ".", admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "archivos-listar", sitio, {"ruta": _ruta(ruta)})


@router.put("/{sitio}/archivos/subir")
async def subir(sitio: str, request: Request, nombre: str, carpeta: str = ".", reemplazar: int = 0,
                admin: dict = Depends(admin_actual)):
    """El cuerpo es el archivo tal cual (como los paquetes). Viaja al intermediario por la carpeta de subidas."""
    sitio, _ = exigir_sitio(admin, sitio)
    destino = _unir(carpeta, nombre)
    guardado = None
    try:
        guardado, total = await subidas.recibir(request, "archivo", config.SUBIDA_MAX_BYTES)
        return await llamar(request, admin, "archivos-subir", sitio,
                            {"ruta": destino, "subida": guardado, "reemplazar": bool(reemplazar)},
                            "sitio_archivo_subir", {"ruta": destino, "bytes": total, "reemplazar": bool(reemplazar)})
    finally:
        subidas.quitar(guardado)  # el intermediario la mueve al usarla; si falló antes, no se deja aquí


@router.post("/{sitio}/archivos/descargar")
async def descargar(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    ruta = _ruta((await cuerpo(request)).get("ruta"), raiz=False)
    datos = await llamar(request, admin, "archivos-descargar", sitio, {"ruta": ruta}, "sitio_archivo_descargar", {"ruta": ruta})
    return descargas.enlace(datos)


@router.post("/{sitio}/archivos/carpeta")
async def carpeta(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    ruta = _ruta((await cuerpo(request)).get("ruta"), raiz=False)
    return await llamar(request, admin, "archivos-carpeta", sitio, {"ruta": ruta}, "sitio_archivo_carpeta", {"ruta": ruta})


async def _par(request: Request, admin: dict, sitio: str, accion: str):
    sitio, _ = exigir_sitio(admin, sitio)
    datos = await cuerpo(request)
    par = {"origen": _ruta(datos.get("origen"), raiz=False), "destino": _ruta(datos.get("destino"), raiz=accion == "descomprimir")}
    return await llamar(request, admin, f"archivos-{accion}", sitio, par, f"sitio_archivo_{accion}", par)


@router.post("/{sitio}/archivos/mover")
async def mover(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    return await _par(request, admin, sitio, "mover")


@router.post("/{sitio}/archivos/copiar")
async def copiar(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    return await _par(request, admin, sitio, "copiar")


@router.post("/{sitio}/archivos/descomprimir")
async def descomprimir(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    return await _par(request, admin, sitio, "descomprimir")


@router.post("/{sitio}/archivos/borrar")
async def borrar(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    ruta = _ruta((await cuerpo(request)).get("ruta"), raiz=False)
    return await llamar(request, admin, "archivos-borrar", sitio, {"ruta": ruta}, "sitio_archivo_borrar", {"ruta": ruta})


@router.post("/{sitio}/archivos/comprimir")
async def comprimir(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    datos = await cuerpo(request)
    lista = datos.get("rutas")
    if not isinstance(lista, list) or not 1 <= len(lista) <= 500:
        raise HTTPException(400, "Elige entre 1 y 500 elementos")
    args = {"rutas": [_ruta(r) for r in lista], "destino": _ruta(datos.get("destino"), raiz=False)}
    return await llamar(request, admin, "archivos-comprimir", sitio, args, "sitio_archivo_comprimir",
                        {"destino": args["destino"], "elementos": len(lista)})


@router.post("/{sitio}/archivos/permisos")
async def permisos(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    datos = await cuerpo(request)
    if datos.get("modo") not in MODOS:
        raise HTTPException(400, "Permisos no admitidos (644, 755, 600, 700, 640 o 750)")
    args = {"ruta": _ruta(datos.get("ruta"), raiz=False), "modo": datos["modo"]}
    return await llamar(request, admin, "archivos-permisos", sitio, args, "sitio_archivo_permisos", args)


@router.get("/{sitio}/archivos/papelera")
async def papelera(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "archivos-papelera", sitio)


@router.post("/{sitio}/archivos/papelera/{elemento}/recuperar")
async def recuperar(sitio: str, elemento: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    if not RE_PAPELERA.fullmatch(elemento):
        raise HTTPException(400, "Elemento no válido")
    return await llamar(request, admin, "archivos-recuperar", sitio, {"id": elemento}, "sitio_archivo_recuperar", {"id": elemento})


@router.delete("/{sitio}/archivos/papelera")
async def vaciar(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "archivos-vaciar", sitio, None, "sitio_archivo_vaciar_papelera")
