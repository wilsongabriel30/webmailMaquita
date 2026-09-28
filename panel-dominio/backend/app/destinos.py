"""A dónde puede entregar un alias, un grupo o un reenvío.

- Dentro de los dominios propios, el destino tiene que existir (una cuenta, un alias o un grupo):
  así no se pierde correo por un error de tecleo.
- Fuera de ellos se acepta cualquier dirección válida: es correo de la organización y ella decide
  a quién se lo reenvía. Queda anotado en la auditoría como destino externo.
"""

from fastapi import HTTPException

from app.validacion import destinos_de_alias


def es_propio(admin: dict, direccion: str) -> bool:
    return direccion.rsplit("@", 1)[1] in admin["dominios"]


async def validar(db, admin: dict, valor, salvo: str = "") -> tuple[list[str], list[str]]:
    """Devuelve (destinos, externos). `salvo` es la propia dirección, que no cuenta como destino."""
    destinos = [d for d in destinos_de_alias(valor) if d != salvo] if valor else []
    propios = [d for d in destinos if es_propio(admin, d)]
    if propios:
        existentes = await db.fetch("SELECT address FROM alias WHERE address = ANY($1::varchar[])", propios)
        faltan = sorted(set(propios) - {f["address"] for f in existentes})
        if faltan:
            raise HTTPException(400, "No existe en tu dominio: " + ", ".join(faltan))
    return destinos, [d for d in destinos if not es_propio(admin, d)]
