"""Listas inteligentes de Tareas (como en To Do) y tareas de una lista, vistas por una persona.

Todas miran las listas que la persona ve (las suyas y las que le compartieron). «Asignado a mí» es la vista de
Seguimiento (app/tareas): aquí no aporta tareas. Devuelven cada tarea con lo que es propio de quien mira: si está en su «Mi día» de hoy. Agregan el nombre de la lista, las
personas asignadas y, si la tarea viene de un correo marcado o soltado en Tareas, el enlace al mensaje
(el del correo soltado solo lo ve quien lo soltó: es su buzón).
"""

from __future__ import annotations

from app.tasks import mi_dia
from app.tasks.acceso import LISTAS_VISIBLES
from app.tasks.schemas import CardOut, CorreoRef
from app.tasks.service import _row_to_card

# $1 = persona, $2 = fecha de hoy en Guayaquil.
_EN_MI_DIA = "EXISTS (SELECT 1 FROM task_mi_dia d WHERE d.card_id = tc.id AND d.user_email = $1 AND d.fecha = $2)"

_SELECT = f"""SELECT tc.*, tl.name AS list_name, {_EN_MI_DIA} AS en_mi_dia,
       COALESCE(co.carpeta, cs.carpeta) AS correo_carpeta, COALESCE(co.uid, cs.uid) AS correo_uid,
       COALESCE(co.asunto, cs.asunto) AS correo_asunto, COALESCE(co.remitente, cs.remitente) AS correo_remitente,
       CASE WHEN co.card_id IS NOT NULL THEN 'marcado' ELSE 'soltado' END AS correo_origen,
       ARRAY(SELECT a.email FROM task_asignados a WHERE a.card_id = tc.id ORDER BY a.asignado_en) AS asignados_todos,
       (SELECT count(*) FROM task_steps s WHERE s.card_id = tc.id) AS pasos_total,
       (SELECT count(*) FROM task_steps s WHERE s.card_id = tc.id AND s.completed) AS pasos_hechos,
       (SELECT count(*) FROM task_adjuntos ad WHERE ad.card_id = tc.id) AS adjuntos_total
  FROM task_cards tc
  JOIN task_lists tl ON tl.id = tc.list_id
  LEFT JOIN task_correo co ON co.card_id = tc.id
  LEFT JOIN task_correo_origen cs ON cs.card_id = tc.id AND cs.user_email = $1
 WHERE tc.list_id IN ({LISTAS_VISIBLES})"""

FILTROS = {
    "my_day": _EN_MI_DIA,
    "important": "tc.important",
    "planned": "(tc.due_date IS NOT NULL OR tc.reminder IS NOT NULL)",
    # «Asignado a mí» es la vista de Seguimiento (SeguimientoVista): aquí no aporta tareas de lista (05/11/2026).
    "assigned": "FALSE",
    "tasks": f"tl.list_type = 'default' AND tc.list_id IN ({LISTAS_VISIBLES})",
    "flagged": f"tl.list_type = 'flagged' AND tc.list_id IN ({LISTAS_VISIBLES})",
}

_ORDEN = {
    "planned": "tc.completed, COALESCE(tc.due_date, tc.reminder), tc.position",
    "flagged": "tc.completed, tc.created_at DESC",
}


def a_tarjeta(row) -> CardOut:
    card = _row_to_card(row)
    card.my_day = bool(row["en_mi_dia"])
    card.list_name = row["list_name"]
    card.asignados = list(row["asignados_todos"] or [])
    card.pasos = row["pasos_total"]
    card.pasos_hechos = row["pasos_hechos"]
    card.adjuntos = row["adjuntos_total"]
    card.seguimiento = bool(row["asignada"])
    if row["correo_uid"] is not None:
        card.correo = CorreoRef(
            carpeta=row["correo_carpeta"],
            uid=row["correo_uid"],
            asunto=row["correo_asunto"],
            remitente=row["correo_remitente"],
            origen=row["correo_origen"],
        )
    return card


async def vista(db, user: str, nombre: str) -> list[CardOut]:
    if nombre not in FILTROS:
        raise ValueError(f"Unknown view: {nombre}")
    orden = _ORDEN.get(nombre, "tc.completed, tc.position")
    rows = await db.fetch(
        f"{_SELECT} AND {FILTROS[nombre]} ORDER BY {orden}", user, mi_dia.hoy()
    )
    return [a_tarjeta(r) for r in rows]


async def de_lista(db, user: str, list_id) -> list[CardOut]:
    """Tareas de una lista (el acceso ya se comprobó)."""
    rows = await db.fetch(
        f"{_SELECT} AND tc.list_id = $3 ORDER BY tc.position",
        user,
        mi_dia.hoy(),
        list_id,
    )
    return [a_tarjeta(r) for r in rows]


async def una(db, user: str, card_id) -> CardOut | None:
    row = await db.fetchrow(f"{_SELECT} AND tc.id = $3", user, mi_dia.hoy(), card_id)
    return a_tarjeta(row) if row else None


MAX_RESULTADOS = 200


# Sin tildes ni diéresis, como en To Do: «accion» encuentra «Acción». La ñ se respeta («año» no es «ano»).
# Sin la extensión unaccent (crearla pide superusuario y las migraciones corren con el usuario de la app).
_CON_TILDE = "áàäâéèëêíìïîóòöôúùüûÁÀÄÂÉÈËÊÍÌÏÎÓÒÖÔÚÙÜÛ"
_SIN_TILDE = "aaaaeeeeiiiioooouuuuAAAAEEEEIIIIOOOOUUUU"
_QUITAR_TILDES = str.maketrans(_CON_TILDE, _SIN_TILDE)


def _sin_tildes(columna: str) -> str:
    return f"translate({columna}, '{_CON_TILDE}', '{_SIN_TILDE}')"


def _patron(texto: str) -> str:
    """Patrón ILIKE que busca el texto tal cual, sin tildes (los comodines del usuario no cuentan)."""
    texto = texto.translate(_QUITAR_TILDES)
    return (
        "%" + texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    )


async def buscar(db, user: str, texto: str) -> list[CardOut]:
    """Tareas de todas las listas visibles cuyo título, nota o algún paso contiene el texto.

    Las de Seguimiento (T-34) tienen su propia vista y no salen aquí.
    """
    rows = await db.fetch(
        f"""{_SELECT} AND NOT tc.asignada
              AND ({_sin_tildes('tc.title')} ILIKE $3 OR {_sin_tildes('tc.note')} ILIKE $3
                   OR EXISTS (SELECT 1 FROM task_steps s
                               WHERE s.card_id = tc.id AND {_sin_tildes('s.title')} ILIKE $3))
            ORDER BY tc.completed, tc.updated_at DESC LIMIT {MAX_RESULTADOS}""",
        user,
        mi_dia.hoy(),
        _patron(texto),
    )
    return [a_tarjeta(r) for r in rows]


async def contar(db, user: str) -> dict[str, int]:
    """Pendientes de cada lista inteligente, con las claves que usa el frontend."""
    fila = await db.fetchrow(
        f"""SELECT count(*) FILTER (WHERE {FILTROS['my_day']})    AS mi_dia,
                  count(*) FILTER (WHERE {FILTROS['important']}) AS importante,
                  count(*) FILTER (WHERE {FILTROS['planned']})   AS planeado,
                  count(*) FILTER (WHERE {FILTROS['tasks']})     AS tareas,
                  count(*) FILTER (WHERE {FILTROS['flagged']})   AS marcado
             FROM task_cards tc
             JOIN task_lists tl ON tl.id = tc.list_id
            WHERE tc.list_id IN ({LISTAS_VISIBLES}) AND tc.completed = FALSE""",
        user,
        mi_dia.hoy(),
    )
    # «Asignado a mí» son las tareas de Seguimiento pendientes de la persona (05/11/2026).
    seguimiento = await db.fetchval(
        """SELECT count(*) FROM task_cards c
             JOIN task_asignados a ON a.card_id = c.id AND a.email = $1
            WHERE c.asignada AND NOT c.completed""",
        user,
    )
    return {
        "my-day": fila["mi_dia"],
        "important": fila["importante"],
        "planned": fila["planeado"],
        "assigned": seguimiento or 0,
        "tasks": fila["tareas"],
        "flagged": fila["marcado"],
    }
