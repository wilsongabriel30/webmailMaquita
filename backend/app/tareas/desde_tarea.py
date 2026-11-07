"""Asignar con seguimiento una tarea que ya existe en una lista (fase 2 de la unificación, 05/11/2026).

«Asignar tarea a:» de una tarea de lista abre el mismo cuadro que Seguimiento. Al guardar, la tarea NO se copia:
pasa a ser una tarea con seguimiento (estados, aceptar o rechazar, recordatorios, aviso al vencer y escalamiento).
Se queda en su lista; quien la asigna pasa a ser quien le da seguimiento (`created_by`, que Seguimiento muestra
como «asignada por»); quien la creó queda en `creada_por`. Las de «Correo marcado» no: van ligadas a un buzón y se asignan desde el correo
(«Asignar como tarea»), que crea una tarea enlazada.
"""

from __future__ import annotations

import json

from app.core.sanitize import sanitize_html, strip_html
from app.tareas.esquemas import PRIORIDADES, RECURRENCIAS, TareaAsignar
from app.tasks import acceso, compartir


class NoSeConvierte(ValueError):
    pass


def _asignados(d: TareaAsignar) -> list[str]:
    vistos: list[str] = []
    for a in d.asignados:
        a = (a or "").strip().lower()
        if a and "@" in a and a not in vistos:
            vistos.append(a)
    return vistos


async def convertir(svc, db, redis, user: str, card_id, d: TareaAsignar):
    tarea = await db.fetchrow(
        """SELECT tc.id, tc.asignada, tl.list_type
             FROM task_cards tc JOIN task_lists tl ON tl.id = tc.list_id WHERE tc.id = $1""",
        card_id,
    )
    if tarea is None or not await acceso.puede_ver_tarea(db, card_id, user):
        raise LookupError("Tarea no encontrada")
    if tarea["asignada"]:
        raise NoSeConvierte("Esta tarea ya tiene seguimiento: se gestiona desde allí")
    if tarea["list_type"] == "flagged":
        raise NoSeConvierte(
            "Las tareas de correo marcado se asignan desde el correo: «Asignar como tarea»"
        )
    asignados = _asignados(d)
    if not asignados:
        raise NoSeConvierte("Elige al menos una persona")
    fuera = [
        a
        for a in asignados
        if not compartir._CORREO.match(a) or not compartir.de_la_casa(a)
    ]
    if fuera:
        raise NoSeConvierte(
            "Solo se puede asignar a personas de la organización: " + ", ".join(fuera)
        )
    if d.recurrencia and d.recurrencia not in RECURRENCIAS:
        raise NoSeConvierte("Recurrencia no válida")
    prioridad = d.prioridad if d.prioridad in PRIORIDADES else "medium"
    estado = "espera" if d.en_espera and d.activa_tarea_id else "pendiente"

    await db.execute(
        """UPDATE task_cards
              SET asignada = TRUE, estado = $2, aceptacion = 'sin_responder', motivo_rechazo = '',
                  completed = FALSE, completed_by = NULL, completed_at = NULL,
                  title = $3, description = $4, due_date = $5, priority = $6, etiquetas = $7::jsonb,
                  recurrence = $8, activa_tarea_id = $9, escalar_a = $10, assigned_to = $11,
                  creada_por = COALESCE(creada_por, created_by), created_by = $12, updated_at = NOW()
            WHERE id = $1""",
        card_id,
        estado,
        strip_html(d.titulo)[:500] or "Tarea",
        sanitize_html(d.descripcion or ""),
        d.plazo,
        prioridad,
        json.dumps(d.etiquetas),
        d.recurrencia,
        d.activa_tarea_id,
        (d.escalar_a or "").lower() or None,
        asignados[0],
        user,
    )
    # Quienes la tenían asignada en la lista y ya no están, salen; los nuevos entran.
    await db.execute(
        "DELETE FROM task_asignados WHERE card_id = $1 AND NOT (email = ANY($2::text[]))",
        card_id,
        asignados,
    )
    for a in asignados:
        await db.execute(
            "INSERT INTO task_asignados (card_id, email, asignado_por) VALUES ($1, $2, $3)"
            " ON CONFLICT DO NOTHING",
            card_id,
            a,
            user,
        )
    pasos = [strip_html(s)[:300] for s in d.subtareas if s.strip()]
    if pasos:
        base = await db.fetchval(
            "SELECT COALESCE(max(position), -1) + 1 FROM task_steps WHERE card_id = $1",
            card_id,
        )
        for i, s in enumerate(pasos):
            await db.execute(
                "INSERT INTO task_steps (card_id, title, position) VALUES ($1, $2, $3)",
                card_id,
                s,
                base + i,
            )
    row = await svc.obtener(db, card_id, user)
    if estado != "espera":
        await svc.anunciar(db, redis, user, row, asignados)
    return row
