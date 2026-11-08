"""Quitar del índice del asistente lo que la persona borra o manda a No deseado desde el webmail.

Hasta el 08/11/2026 un correo eliminado seguía en el índice hasta la pasada nocturna siguiente
(que lo detecta ausente de la carpeta). Ahora las acciones del propio webmail (eliminar, mover,
informar como no deseado) lo quitan al instante; lo que se borra desde otros clientes (Outlook,
teléfono) lo recoge la pasada nocturna, como antes. Nunca falla la acción del correo por esto.
"""

import logging

from app.rag import almacen, omitidos

logger = logging.getLogger(__name__)

# Acciones del webmail tras las cuales el correo ya no está en la carpeta de origen.
ACCIONES_QUE_QUITAN = frozenset({"delete", "move", "archive"})


async def quitar(db, username: str, folder: str, uids) -> int:
    """Borra las filas (índice y omitidos) de esos UID de la carpeta. Devuelve cuántas quitó."""
    lista = [str(u) for u in uids or () if str(u).strip()]
    if not lista or db is None:
        return 0
    try:
        n = await almacen.borrar_uids(db, username, folder, lista)
        await omitidos.borrar_uids(db, username, folder, lista)
        return n
    except Exception as e:  # el índice es secundario: la acción del correo ya se hizo
        logger.debug(
            "RAG %s: no se pudo quitar del índice %s/%s: %s",
            username,
            folder,
            lista[:5],
            e,
        )
        return 0


async def tras_accion(db, username: str, folder: str, uids, accion: str) -> int:
    if accion not in ACCIONES_QUE_QUITAN:
        return 0
    return await quitar(db, username, folder, uids)
