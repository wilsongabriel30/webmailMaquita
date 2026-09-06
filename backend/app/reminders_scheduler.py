"""Recordatorios de tareas y eventos de calendario.

Bucle de fondo (cada 60 s) con RECLAMO ATÓMICO (UPDATE … RETURNING), seguro
con múltiples workers: cada recordatorio se publica exactamente una vez.
- Tareas: task_cards.reminder vencido (ventana 1 h) y no completado.
- Eventos: aviso N minutos antes de dtstart (reminders[0].minutes o 15 por
  defecto; se omiten día completo y recurrentes).
Publica en Redis (ws:user:<owner>) con type="reminder" → el frontend muestra
toast + sonido + Notification del navegador.
"""
import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

import aiosmtplib

logger = logging.getLogger("reminders")

_DDL_LOCK = 815001  # advisory lock para DDL una sola vez entre workers

DDL = [
    "ALTER TABLE task_cards ADD COLUMN IF NOT EXISTS reminder_sent BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE events ADD COLUMN IF NOT EXISTS reminder_sent_at TIMESTAMPTZ",
]

CLAIM_TASKS = """
UPDATE task_cards c SET reminder_sent = TRUE
FROM task_lists l
WHERE l.id = c.list_id
  AND c.reminder IS NOT NULL
  AND c.reminder <= $1
  AND c.reminder > $1 - interval '1 hour'
  AND c.completed = FALSE
  AND c.reminder_sent = FALSE
RETURNING c.id, c.title, l.owner
"""

CLAIM_EVENTS = """
UPDATE events e SET reminder_sent_at = $1
FROM calendars c
WHERE c.id = e.calendar_id
  AND e.dtstart > $1
  AND e.dtstart <= $1 + interval '12 hours'
  AND e.all_day = FALSE
  AND COALESCE(e.rrule, '') = ''
  AND e.status <> 'CANCELLED'
  AND e.reminder_sent_at IS NULL
  AND e.dtstart - (COALESCE(NULLIF(e.reminders->0->>'minutes', '')::int, 15)
                   * interval '1 minute') <= $1
RETURNING e.id, e.summary, e.dtstart, c.owner_email
"""


async def _send_fallback_email(username: str, message: str):
    """Si el usuario no tiene el webmail abierto, el recordatorio llega por correo."""
    try:
        from app.branding.service import app_name_cacheado
        from app.config import get_settings
        st = get_settings()
        msg = EmailMessage()
        msg["From"] = f"no-reply@{st.mail_domain}"
        msg["To"] = username
        msg["Subject"] = message[:140]
        msg.set_content(message)
        msg.add_alternative(
            f"<p style=\"font-size:14px\">{message}</p>"
            f"<p style=\"color:#605e5c;font-size:12px\">Recordatorio automático de {app_name_cacheado()} "
            f"(recibiste este correo porque no tenías el webmail abierto).</p>",
            subtype="html",
        )
        # Relay local de Postfix (sin auth desde localhost)
        await aiosmtplib.send(msg, hostname="127.0.0.1", port=25, timeout=20, start_tls=False)
        logger.info("Recordatorio enviado por correo a %s", username)
    except Exception as exc:
        logger.warning("Fallback de correo a %s: %s", username, exc)


async def _publish(redis, username: str, message: str, tag: str, kind: str = "", entity_id: str = ""):
    try:
        await redis.publish(
            f"ws:user:{username}",
            json.dumps({"type": "reminder", "message": message, "tag": tag,
                        "kind": kind, "entity_id": str(entity_id)}),
        )
    except Exception as exc:
        logger.warning("No se pudo publicar recordatorio a %s: %s", username, exc)
    try:
        online = await redis.exists(f"presence:{username}")
    except Exception:
        online = True
    if not online:
        await _send_fallback_email(username, message)


def _fmt_hora(dt: datetime) -> str:
    try:
        from zoneinfo import ZoneInfo
        return dt.astimezone(ZoneInfo("America/Guayaquil")).strftime("%H:%M")
    except Exception:
        return dt.strftime("%H:%M")


async def check_reminders(app):
    """Bucle principal de recordatorios (seguro multi-worker)."""
    db = app.state.db_pool
    redis = app.state.redis
    ddl_listo = False

    while True:
        try:
            await asyncio.sleep(60)
            if not ddl_listo:
                # DDL diferido (post-arranque) y serializado entre workers
                async with db.acquire() as conn:
                    await conn.execute("SELECT pg_advisory_lock($1)", _DDL_LOCK)
                    try:
                        for stmt in DDL:
                            await conn.execute(stmt)
                    finally:
                        await conn.execute("SELECT pg_advisory_unlock($1)", _DDL_LOCK)
                ddl_listo = True
            now = datetime.now(timezone.utc)

            rows = await db.fetch(CLAIM_TASKS, now)
            for r in rows:
                await _publish(
                    redis, r["owner"],
                    f"⏰ Recordatorio de tarea: {r['title']}",
                    f"task-rem-{r['id']}",
                    kind="task", entity_id=r["id"],
                )

            rows = await db.fetch(CLAIM_EVENTS, now)
            for r in rows:
                await _publish(
                    redis, r["owner_email"],
                    f"📅 {r['summary']} empieza a las {_fmt_hora(r['dtstart'])}",
                    f"event-rem-{r['id']}",
                    kind="event", entity_id=r["id"],
                )

            # ── Eventos RECURRENTES: próxima ocurrencia ──
            try:
                from dateutil.rrule import rrulestr
                recs = await db.fetch(
                    """SELECT e.id, e.summary, e.dtstart, e.rrule, e.reminders,
                              e.reminder_sent_at, c.owner_email
                       FROM events e JOIN calendars c ON c.id = e.calendar_id
                       WHERE COALESCE(e.rrule, '') <> ''
                         AND e.all_day = FALSE
                         AND e.status <> 'CANCELLED'
                       LIMIT 500"""
                )
                for r in recs:
                    tzinfo = r["dtstart"].tzinfo
                    base = r["dtstart"].replace(tzinfo=None)
                    try:
                        rule = rrulestr(
                            f"DTSTART:{base.strftime('%Y%m%dT%H%M%S')}\n{r['rrule']}",
                            ignoretz=True,
                        )
                    except Exception:
                        continue
                    now_naive = now.astimezone(tzinfo).replace(tzinfo=None) if tzinfo else now.replace(tzinfo=None)
                    occ = rule.after(now_naive - timedelta(minutes=1), inc=True)
                    if occ is None:
                        continue
                    occ_aware = occ.replace(tzinfo=tzinfo) if tzinfo else occ.replace(tzinfo=timezone.utc)
                    minutos = 15
                    rem = r["reminders"]
                    if isinstance(rem, str):
                        try:
                            rem = json.loads(rem)
                        except Exception:
                            rem = []
                    if rem and isinstance(rem, list):
                        p0 = rem[0]
                        if isinstance(p0, dict) and p0.get("minutes"):
                            try:
                                minutos = int(p0["minutes"])
                            except Exception:
                                pass
                    if now < occ_aware - timedelta(minutes=minutos) or now >= occ_aware:
                        continue
                    claimed = await db.fetchrow(
                        """UPDATE events SET reminder_sent_at = $1
                           WHERE id = $2
                             AND (reminder_sent_at IS NULL OR reminder_sent_at < $1)
                           RETURNING id""",
                        occ_aware, r["id"],
                    )
                    if claimed:
                        await _publish(
                            redis, r["owner_email"],
                            f"📅 {r['summary']} empieza a las {_fmt_hora(occ_aware)}",
                            f"event-rem-{r['id']}-{occ_aware.isoformat()}",
                            kind="event", entity_id=r["id"],
                        )
            except Exception as exc:
                logger.error("Error en recordatorios recurrentes: %s", exc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Error en bucle de recordatorios: %s", exc)
