"""«Mi sitio web»: los sitios de los dominios asignados, a través del intermediario root.

El portal no tiene privilegios (ni sudo ni capacidades): todo lo que toca el sistema lo pide por
un socket Unix a maquita-sitios-portal, que vuelve a comprobar la sesión y el alcance.
"""

from fastapi import APIRouter

from app.sitios import (
    aplicacion,
    archivos,
    avanzado,
    baja,
    bases,
    copias,
    datos,
    ddns,
    descargas,
    dominios_alias,
    ficha,
    git,
    ftp_cuentas,
    https_ftp,
    inicio,
    paquete,
    propias,
    servidor,
    tareas,
    web,
    zona,
)

router = APIRouter()
# El orden importa: /api/sitios/dns/…, /api/sitios/resumen, /api/sitios/servidor y /api/sitios/descargas/… van
# antes que /api/sitios/{sitio}/…
for _modulo in (zona, ddns, inicio, servidor, descargas, ficha, aplicacion, https_ftp, tareas, bases, avanzado, paquete,
                baja, web, ftp_cuentas, archivos, datos, copias, dominios_alias, propias, git):
    router.include_router(_modulo.router)
