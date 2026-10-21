"""Trabajos de cron del sitio: ver, guardar la lista, ejecutar ahora y ver la salida.

Corren con el usuario del sitio y encerrados (lo hace maquita-sitios). En la auditoría queda la
orden recortada, que es lo que hace falta para saber quién programó qué.
"""

from fastapi import APIRouter, Depends, Request

from app.sesion import admin_actual
from app.sitios import validacion as v
from app.sitios.comun import cuerpo, exigir_sitio, llamar

router = APIRouter(prefix="/api/sitios", tags=["sitios"])


@router.get("/{sitio}/tareas")
async def ver(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "tareas", sitio)


@router.put("/{sitio}/tareas")
async def guardar(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    lista = v.trabajos((await cuerpo(request)).get("trabajos"))
    resumen = [{"horario": t["horario"], "orden": t["orden"][:200], "activo": t["activo"]} for t in lista]
    return await llamar(request, admin, "tareas-guardar", sitio, {"lista": lista}, "sitio_cron_guardar", {"trabajos": resumen})


@router.post("/{sitio}/tareas/{tarea}/ejecutar")
async def ejecutar(sitio: str, tarea: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    tarea = v.con_forma(v.RE_TAREA, tarea, "Trabajo no válido")
    return await llamar(request, admin, "tarea-ejecutar", sitio, {"id": tarea}, "sitio_cron_ejecutar", {"id": tarea})


@router.get("/{sitio}/tareas/{tarea}/registro")
async def registro(sitio: str, tarea: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    return await llamar(request, admin, "tarea-registro", sitio, {"id": v.con_forma(v.RE_TAREA, tarea, "Trabajo no válido")})
