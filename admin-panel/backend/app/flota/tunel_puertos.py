"""Puerto remoto de cada equipo en el servidor de túneles (uno por equipo, 22001-22999).

No hay tabla aparte: el puerto de un equipo es el de su última orden `abrir_tunel_soporte`. Así el
reparto queda en el mismo sitio que la auditoría y no hace falta ninguna migración. Los equipos
retirados liberan su puerto.
"""

from __future__ import annotations

from fastapi import HTTPException

from app.flota.tunel_ajustes import ABRIR, PUERTO_MAX, PUERTO_MIN

SQL_MAPA = (
    "SELECT DISTINCT ON (o.equipo_id) o.equipo_id::text AS equipo_id, e.nombre, "
    "(o.parametros->>'puerto_remoto')::int AS puerto "
    "FROM flota_ordenes o JOIN flota_equipos e ON e.equipo_id = o.equipo_id "
    f"WHERE o.tipo = '{ABRIR}' AND o.parametros ? 'puerto_remoto' AND e.estado = 'activo' "
    "ORDER BY o.equipo_id, o.emitida_en DESC"
)
SQL_CANDADO = "SELECT pg_advisory_xact_lock(hashtext('flota_tunel_puertos'))"


async def mapa(conexion) -> dict[str, dict]:
    """equipo_id → {puerto, nombre} de los equipos activos que ya tienen puerto."""
    return {
        f["equipo_id"]: {"puerto": f["puerto"], "nombre": f["nombre"]}
        for f in await conexion.fetch(SQL_MAPA)
    }


def menor_libre(ocupados) -> int:
    ocupados = set(ocupados)
    for puerto in range(PUERTO_MIN, PUERTO_MAX + 1):
        if puerto not in ocupados:
            return puerto
    raise HTTPException(
        409,
        f"No quedan puertos libres para túneles ({PUERTO_MIN}-{PUERTO_MAX}): retire equipos que ya no se usen.",
    )


def de_otros(asignados: dict[str, dict], equipo_id: str) -> dict[int, str]:
    """puerto → nombre del equipo que lo tiene, sin contar a `equipo_id`."""
    return {a["puerto"]: a["nombre"] for e, a in asignados.items() if e != equipo_id}


async def asignar(conexion, equipo_id: str, pedido: int | None) -> int:
    """El puerto pedido (si no es de otro equipo), el que ya tenía el equipo o el menor libre.

    Debe llamarse dentro de una transacción: el candado evita que dos emisiones a la vez repartan el
    mismo puerto."""
    await conexion.execute(SQL_CANDADO)
    asignados = await mapa(conexion)
    ajenos = de_otros(asignados, equipo_id)
    if pedido is not None:
        if pedido in ajenos:
            raise HTTPException(
                409,
                f"El puerto {pedido} ya está asignado al equipo {ajenos[pedido]}: elija otro.",
            )
        return pedido
    if equipo_id in asignados:
        return asignados[equipo_id]["puerto"]
    return menor_libre(ajenos)
