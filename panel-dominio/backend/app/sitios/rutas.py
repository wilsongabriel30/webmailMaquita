"""«Mi sitio web»: los sitios de los dominios asignados, a través del intermediario root.

El portal no tiene privilegios (ni sudo ni capacidades): todo lo que toca el sistema lo pide por
un socket Unix a maquita-sitios-portal, que vuelve a comprobar la sesión y el alcance.
"""

from fastapi import APIRouter

from app.sitios import aplicacion, avanzado, bases, baja, ficha, https_ftp, inicio, paquete, tareas, zona

router = APIRouter()
# El orden importa: /api/sitios/dns/… y /api/sitios/resumen van antes que /api/sitios/{sitio}/…
for _modulo in (zona, inicio, ficha, aplicacion, https_ftp, tareas, bases, avanzado, paquete, baja):
    router.include_router(_modulo.router)
