"""Al borrar el organizador, desaparecen las copias de los asistentes (05/11/2026).

Antes el evento se borraba solo del calendario del organizador; cada invitado conservaba su
copia (recibía el correo de cancelación, pero el evento seguía en su calendario). Si quien
borra NO es el organizador (un asistente quita su copia), no se toca nada más.
"""

import json
import logging

from app.calendar.radicale_client import radicale_client

log = logging.getLogger("calendar.cascada")


def _organizador(attendees, dueno: str) -> str:
    if isinstance(attendees, str):
        attendees = json.loads(attendees or "[]")
    for a in attendees or []:
        if (
            isinstance(a, dict)
            and (a.get("role") or "").upper() == "ORGANIZER"
            and a.get("email")
        ):
            return a["email"].lower()
    return (dueno or "").lower()


async def borrar_copias(db, uid: str, dueno: str, attendees, event_id) -> int:
    """Borra las demás copias del `uid` si `dueno` es el organizador. Devuelve cuántas."""
    if not uid or _organizador(attendees, dueno) != (dueno or "").lower():
        return 0
    copias = await db.fetch(
        """SELECT e.id, c.owner_email, c.radicale_path FROM events e
           JOIN calendars c ON c.id = e.calendar_id WHERE e.uid = $1 AND e.id <> $2""",
        uid,
        event_id,
    )
    for c in copias:
        try:
            await radicale_client.delete_event(
                c["owner_email"], c["radicale_path"], uid
            )
        except Exception as e:  # noqa: BLE001
            log.warning(
                "copia %s de %s: Radicale no la borró: %s", uid, c["owner_email"], e
            )
        await db.execute("DELETE FROM events WHERE id = $1", c["id"])
    return len(copias)
