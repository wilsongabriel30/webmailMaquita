"""Alias de dominio de un sitio (v1.11): otros nombres de tus dominios que muestran el mismo sitio.

La lista que llega reemplaza a la anterior (vacía: sin alias). Aquí se comprueba que cada alias sea uno de los
dominios asignados o un subdominio suyo, para no llamar siquiera al intermediario con un nombre ajeno; el
intermediario lo vuelve a comprobar todo (también los nombres reservados y los que ya usa otro sitio).
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.sesion import admin_actual
from app.sitios.comun import RE_SITIO, cuerpo, dominio_de, exigir_sitio, llamar

router = APIRouter(prefix="/api/sitios", tags=["sitios"])
MAXIMO = 10


def limpiar(admin: dict, lista) -> list[str]:
    if not isinstance(lista, list) or len(lista) > MAXIMO:
        raise HTTPException(400, f"Se admiten hasta {MAXIMO} alias por sitio")
    limpias = []
    for valor in lista:
        if not isinstance(valor, str):
            raise HTTPException(400, "Cada alias es un nombre de dominio")
        nombre = valor.strip().lower().removeprefix("www.")
        if not nombre:
            continue
        if not RE_SITIO.fullmatch(nombre):
            raise HTTPException(400, f"Nombre no válido: {nombre[:80]}")
        if not dominio_de(admin, nombre):
            raise HTTPException(400, f"{nombre} no es de tus dominios: un alias tiene que ser uno de los dominios "
                                     "que administras o un subdominio suyo")
        if nombre not in limpias:
            limpias.append(nombre)
    return limpias


@router.put("/{sitio}/alias")
async def guardar(sitio: str, request: Request, admin: dict = Depends(admin_actual)):
    sitio, _ = exigir_sitio(admin, sitio)
    lista = limpiar(admin, (await cuerpo(request)).get("alias"))
    return await llamar(request, admin, "alias", sitio, {"alias": lista}, "sitio_alias", {"alias": lista})
