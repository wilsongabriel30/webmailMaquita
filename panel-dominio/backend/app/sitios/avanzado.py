"""Avanzado del sitio: ajustes de PHP, versión de PHP (solo las ya instaladas), archivos de la
aplicación y vuelta a una versión anterior.

Desde el portal no hay reglas propias de nginx ni se instalan versiones o extensiones de PHP:
eso afecta al servidor entero y lo hace el administrador general. Antes de cada cambio,
maquita-sitios guarda la versión anterior y comprueba la configuración.
"""

from fastapi import APIRouter, Depends, Request

from app.sesion import admin_actual
from app.sitios import config, subidas
from app.sitios import validacion as v
from app.sitios.comun import cuerpo, exigir_sitio, llamar

router = APIRouter(prefix="/api/sitios", tags=["sitios"])


@router.get("/{sitio}/avanzado")
async def ver(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "avanzado", sitio)


@router.get("/{sitio}/php")
async def php_estado(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    """Versión del sitio y versiones ya instaladas a las que se puede pasar."""
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "php-estado", sitio)


@router.put("/{sitio}/php")
async def php_ajustes(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    ajustes = v.ajustes_php((await cuerpo(request)).get("ajustes"))
    return await llamar(request, admin, "avanzado-php", sitio, {"ajustes": ajustes}, "sitio_avanzado_php", ajustes)


@router.put("/{sitio}/php/version")
async def php_version(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    version = v.con_forma(v.RE_VERSION_PHP, (await cuerpo(request)).get("version"), "Versión de PHP no válida")
    return await llamar(request, admin, "php-version", sitio, {"version": version}, "sitio_php_version", {"version": version})


@router.get("/{sitio}/archivo")
async def archivo_ver(sitio: str, ruta: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "avanzado-ver", sitio, {"ruta": v.ruta_archivo(ruta)})


@router.put("/{sitio}/archivo")
async def archivo_guardar(sitio: str, ruta: str, request: Request, admin: dict = Depends(admin_actual)):
    """El cuerpo es el texto del archivo tal cual. Viaja al intermediario por la carpeta de subidas."""
    sitio, _ = exigir_sitio(admin, sitio)
    ruta = v.ruta_archivo(ruta)
    nombre, total = await subidas.recibir(request, "texto", config.ARCHIVO_MAX_BYTES)
    try:
        return await llamar(request, admin, "avanzado-archivo", sitio, {"ruta": ruta, "subida": nombre},
                            "sitio_avanzado_archivo", {"ruta": ruta, "bytes": total})
    finally:
        subidas.quitar(nombre)


@router.post("/{sitio}/restaurar")
async def restaurar(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    version = v.con_forma(v.RE_VERSION_COPIA, (await cuerpo(request)).get("version"), "Versión no válida")
    return await llamar(request, admin, "avanzado-restaurar", sitio, {"version": version},
                        "sitio_avanzado_restaurar", {"version": version})
