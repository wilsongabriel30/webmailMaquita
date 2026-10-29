"""«Correo marcado» de Tareas (como en To Do): cada correo con bandera de la Bandeja de entrada es una tarea.

Sincroniza en los dos sentidos sin tocar el módulo de correo:
- Al abrir Tareas o la vista, se compara con el buzón. Si un correo marcado no tiene tarea, se crea.
  Si a un correo le quitaron la bandera, o ya no está en la Bandeja de entrada, su tarea queda
  completada. Si lo volvieron a marcar, se reabre.
- Completar la tarea le quita la bandera al correo y reabrirla se la vuelve a poner. Borrarla también
  le quita la bandera.

Las tareas viven en una lista propia de cada persona, que no sale entre «Mis listas»
(list_type = 'flagged'). Cada tarea guarda a qué mensaje apunta en `task_correo`.
"""

from __future__ import annotations

import logging

from app.core.sanitize import strip_html
from app.tasks import acceso
from app.tasks.service import task_service

logger = logging.getLogger(__name__)

CARPETA = "INBOX"
MAX_CORREOS = (
    200  # los marcados más recientes; si hay más, no se completa nada por ausencia
)


async def _conectar(request, user: str):
    from app.core.session import get_imap_login_user, get_user_password
    from app.mail.clients.imap_client import get_imap_connection

    password = await get_user_password(request, user)
    login_user = await get_imap_login_user(request, user)
    return await get_imap_connection(login_user, password)


async def _cerrar(imap) -> None:
    try:
        await imap.logout()
    except Exception:
        pass


def _clave(message_id: str, uid: int) -> str:
    return (message_id or "").strip() or f"uid:{uid}"


async def asegurar_lista(db, user: str):
    board_id = await task_service.ensure_default_board(db, user)
    list_id = await db.fetchval(
        "SELECT id FROM task_lists WHERE board_id = $1 AND list_type = 'flagged' ORDER BY position LIMIT 1",
        board_id,
    )
    if list_id:
        return list_id, board_id
    list_id = await db.fetchval(
        """INSERT INTO task_lists (board_id, name, position, color, list_type, icon, owner)
           VALUES ($1, 'Correo electrónico marcado', 0, '#e0e0e0', 'flagged', '', $2) RETURNING id""",
        board_id,
        user,
    )
    await acceso.registrar_propietaria(db, list_id, user)
    return list_id, board_id


async def aplicar(
    con, user: str, marcados: list[dict], completo: bool
) -> dict[str, int]:
    """Deja las tareas como dicen los correos marcados. `con` va dentro de una transacción."""
    await con.execute(
        "SELECT pg_advisory_xact_lock(hashtext($1))", "tareas-correo:" + user
    )
    list_id, board_id = await asegurar_lista(con, user)
    filas = await con.fetch(
        """SELECT co.card_id, co.message_id, co.uid, tc.completed, tc.title
             FROM task_correo co JOIN task_cards tc ON tc.id = co.card_id
            WHERE co.user_email = $1 AND co.carpeta = $2""",
        user,
        CARPETA,
    )
    existentes = {_clave(f["message_id"], f["uid"]): f for f in filas}
    cambios = {"creadas": 0, "reabiertas": 0, "completadas": 0}
    vistos: set[str] = set()
    for m in marcados:
        uid = int(m.get("uid") or 0)
        if not uid:
            continue
        message_id = (m.get("message_id") or "").strip()
        clave = _clave(message_id, uid)
        vistos.add(clave)
        fila = existentes.get(clave)
        if fila is None:
            titulo = strip_html(m.get("subject") or "").strip()[:500] or "(sin asunto)"
            posicion = await con.fetchval(
                "SELECT COALESCE(MAX(position), -1) + 1 FROM task_cards WHERE list_id = $1",
                list_id,
            )
            card_id = await con.fetchval(
                """INSERT INTO task_cards (list_id, title, description, created_by, position)
                   VALUES ($1, $2, '', $3, $4) RETURNING id""",
                list_id,
                titulo,
                user,
                posicion,
            )
            await con.execute(
                """INSERT INTO task_correo (card_id, user_email, carpeta, uid, message_id, asunto, remitente)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                card_id,
                user,
                CARPETA,
                uid,
                message_id,
                titulo,
                strip_html(m.get("from") or "")[:300],
            )
            await task_service._log_activity(
                con,
                board_id,
                user,
                "card_created",
                f"Tarea '{titulo}' creada desde un correo marcado",
                card_id,
            )
            cambios["creadas"] += 1
            continue
        if fila["uid"] != uid:
            await con.execute(
                "UPDATE task_correo SET uid = $2 WHERE card_id = $1",
                fila["card_id"],
                uid,
            )
        if fila["completed"]:
            await con.execute(
                """UPDATE task_cards SET completed = FALSE, completed_by = NULL, completed_at = NULL,
                          updated_at = NOW() WHERE id = $1""",
                fila["card_id"],
            )
            await task_service._log_activity(
                con,
                board_id,
                user,
                "card_toggled",
                f"'{fila['title']}' reabierta: el correo volvió a tener bandera",
                fila["card_id"],
            )
            cambios["reabiertas"] += 1
    if completo:
        for clave, fila in existentes.items():
            if clave in vistos or fila["completed"]:
                continue
            await con.execute(
                """UPDATE task_cards SET completed = TRUE, completed_by = $2, completed_at = NOW(),
                          updated_at = NOW() WHERE id = $1""",
                fila["card_id"],
                user,
            )
            await task_service._log_activity(
                con,
                board_id,
                user,
                "card_toggled",
                f"'{fila['title']}' completada: el correo ya no tiene bandera",
                fila["card_id"],
            )
            cambios["completadas"] += 1
    return cambios


async def sincronizar(request, user: str) -> None:
    """Compara con el buzón. Si el correo no responde, las tareas quedan como estaban."""
    from app.mail.services.message_service import list_messages

    try:
        imap = await _conectar(request, user)
    except Exception:
        logger.warning(
            "Correo marcado: no se pudo conectar al buzón de %s", user, exc_info=True
        )
        return
    try:
        resultado = await list_messages(imap, CARPETA, 1, MAX_CORREOS, "is:flagged")
    except Exception:
        logger.warning(
            "Correo marcado: no se pudo leer el buzón de %s", user, exc_info=True
        )
        return
    finally:
        await _cerrar(imap)
    if resultado is None:
        return
    marcados = resultado.get("messages") or []
    completo = int(resultado.get("total") or 0) <= MAX_CORREOS
    pool = request.app.state.db_pool
    async with pool.acquire() as con:
        async with con.transaction():
            await aplicar(con, user, marcados, completo)


async def vinculo(db, card_id, user: str):
    """Mensaje al que apunta la tarea, si viene de un correo marcado de esta persona."""
    return await db.fetchrow(
        "SELECT carpeta, uid FROM task_correo WHERE card_id = $1 AND user_email = $2",
        card_id,
        user,
    )


async def poner_bandera(request, user: str, enlace, marcado: bool) -> None:
    """Refleja en el correo lo que se hizo con la tarea (completar = quitar la bandera)."""
    if not enlace:
        return
    from app.mail.clients.imap_client import uid_set_flags

    try:
        imap = await _conectar(request, user)
    except Exception:
        logger.warning(
            "Correo marcado: no se pudo conectar al buzón de %s", user, exc_info=True
        )
        return
    try:
        await uid_set_flags(
            imap, enlace["carpeta"], int(enlace["uid"]), "\\Flagged", add=marcado
        )
    except Exception:
        logger.warning(
            "Correo marcado: no se pudo cambiar la bandera (%s)", user, exc_info=True
        )
    finally:
        await _cerrar(imap)
    try:  # la lista de carpetas y los contadores del correo se vuelven a pedir
        redis = request.app.state.redis
        await redis.delete(f"folders:{user}")
        await redis.delete(f"stats:{user}")
    except Exception:
        pass
