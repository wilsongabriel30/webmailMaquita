"""Asignaciones de etiqueta cuyo correo IMAP ya no devuelve: marca «faltante» y cuenta coherente (09/11/2026).

`message_labels.faltante_desde` (migración 2026-11-09-etiquetas-faltantes.sql):
- NULL: la asignación se considera vigente; cuenta en el contador lateral y en el `total` del listado.
- Fecha: al listar la etiqueta, IMAP no devolvió ese correo (carpeta seleccionada bien, uid ausente).
  No cuenta ni se lista. Se limpia en cuanto el correo vuelve a verse en su carpeta (p. ej. al pedir las
  etiquetas de los uids visibles de una carpeta). `etiquetas_huerfanas` borra las que llevan más de 7 días.

Marcar NO es borrar: un fallo pasajero de IMAP (carpeta no seleccionable, error de red) no marca nada.
"""

import logging

log = logging.getLogger("maquita.webmail.etiquetas")


def faltantes_de_pagina(
    pedidos: dict[str, list[int]], devueltos: dict[str, set[int]]
) -> list[tuple[str, int]]:
    """(carpeta, uid) pedidos a IMAP que no volvieron. Solo de carpetas que SÍ respondieron
    (una carpeta ausente en `devueltos` no se pudo consultar: no se marca)."""
    faltan: list[tuple[str, int]] = []
    for carpeta, uids in pedidos.items():
        if carpeta not in devueltos:
            continue
        vistos = devueltos[carpeta]
        faltan.extend((carpeta, u) for u in uids if u not in vistos)
    return faltan


async def marcar_faltantes(
    db, owner: str, label_id: int, faltan: list[tuple[str, int]]
) -> int:
    """Pone `faltante_desde = now()` (solo si estaba NULL, para conservar la primera fecha)."""
    if not faltan or db is None:
        return 0
    n = 0
    for carpeta, uid in faltan:
        r = await db.execute(
            """UPDATE message_labels SET faltante_desde = now()
               WHERE owner = $1 AND label_id = $2 AND folder = $3 AND message_uid = $4 AND faltante_desde IS NULL""",
            owner,
            label_id,
            carpeta,
            uid,
        )
        if str(r).endswith(" 1"):
            n += 1
    if n:
        log.info(
            "etiquetas: %s etiqueta %d: %d asignaciones marcadas como faltantes",
            owner,
            label_id,
            n,
        )
    return n


async def limpiar_faltantes_vistos(db, owner: str, folder: str, uids: list[int]) -> int:
    """El correo volvió a verse en su carpeta: la asignación deja de ser faltante."""
    if not uids or db is None:
        return 0
    r = await db.execute(
        """UPDATE message_labels SET faltante_desde = NULL
           WHERE owner = $1 AND folder = $2 AND message_uid = ANY($3::int[]) AND faltante_desde IS NOT NULL""",
        owner,
        folder,
        uids,
    )
    try:
        return int(str(r).split()[-1])
    except (ValueError, IndexError):
        return 0


async def contar_vigentes(db, owner: str, label_id: int) -> int:
    return await db.fetchval(
        "SELECT COUNT(*) FROM message_labels WHERE label_id = $1 AND owner = $2 AND faltante_desde IS NULL",
        label_id,
        owner,
    )


async def contar_vigentes_por_etiqueta(db, owner: str) -> dict[int, int]:
    """{label_id: asignaciones vigentes} de todas las etiquetas de la cuenta, en una sola consulta."""
    filas = await db.fetch(
        """SELECT label_id, COUNT(*) AS n FROM message_labels
           WHERE owner = $1 AND faltante_desde IS NULL GROUP BY label_id""",
        owner,
    )
    return {f["label_id"]: f["n"] for f in filas}
