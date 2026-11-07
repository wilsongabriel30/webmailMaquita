"""Avisos de las listas compartidas (como en To Do, F4 30/10/2026).

- Dentro del webmail: por el WebSocket de cada persona (Redis `ws:user:<correo>`, tipo `task_notification`), que ya
  muestra el aviso, suena y, si la persona lo permitió, saca la notificación del navegador.
- Por correo, solo a quien lo pidió (`task_preferencias.avisos_correo`); se usa el mismo envío que Seguimiento.
- Tiempo real: cuando cambia algo de una lista compartida, a las demás personas les llega `tareas_cambio` (sin aviso
  visible) y su pantalla se pone al día.

Un aviso que no sale no rompe la operación.
"""

from __future__ import annotations

import json
import logging

from app import organizacion
from app.tareas import avisos

logger = logging.getLogger(__name__)


def url_tareas() -> str:
    return organizacion.url_correo() + "/webmail/tasks"


async def quiere_correo(db, user: str) -> bool:
    return bool(
        await db.fetchval(
            "SELECT avisos_correo FROM task_preferencias WHERE user_email = $1", user
        )
    )


async def guardar_preferencia(db, user: str, avisos_correo: bool) -> None:
    await db.execute(
        """INSERT INTO task_preferencias (user_email, avisos_correo) VALUES ($1, $2)
           ON CONFLICT (user_email) DO UPDATE SET avisos_correo = EXCLUDED.avisos_correo, cambiado_en = NOW()""",
        user,
        avisos_correo,
    )


async def avisar(
    redis,
    db,
    destinatarios,
    por: str,
    accion: str,
    titulo: str,
    texto: str,
    task_id=None,
    correo: bool = False,
) -> None:
    """Aviso a cada destinataria (nunca a quien hizo el cambio).

    `correo=True` lo manda también por correo aunque la persona no lo haya pedido (asignarle una tarea a alguien).
    """
    for d in sorted({d for d in destinatarios if d and d != por}):
        try:
            await redis.publish(
                "ws:user:" + d,
                json.dumps(
                    {
                        "type": "task_notification",
                        "action": accion,
                        "task_id": str(task_id) if task_id else "",
                        "by_user": por,
                        "message": texto,
                    }
                ),
            )
        except Exception:
            logger.warning(
                "Aviso de lista compartida no enviado a %s", d, exc_info=True
            )
        try:
            if correo or await quiere_correo(db, d):
                await avisos._correo([d], titulo, texto, url_tareas())
        except Exception:
            logger.warning(
                "Correo de aviso de lista compartida no enviado a %s", d, exc_info=True
            )


async def cambio(redis, destinatarios, list_ids) -> None:
    """Pide a las pantallas de esas personas que vuelvan a cargar sus tareas."""
    mensaje = json.dumps(
        {"type": "tareas_cambio", "listas": [str(i) for i in list_ids]}
    )
    for d in destinatarios:
        try:
            await redis.publish("ws:user:" + d, mensaje)
        except Exception:
            logger.debug("tareas_cambio no enviado a %s", d, exc_info=True)
