"""Respuestas a invitaciones visibles para el organizador (05/11/2026).

Cada asistente tiene su propia copia del evento (mismo `uid`, otro `id`). La respuesta se
guardaba solo contra la copia del asistente, así que el organizador nunca veía quién aceptó.
Aquí se propaga a TODAS las copias del `uid`: tabla `event_invitations` y el campo `status`
del asistente dentro de `events.attendees` (es lo que `ical_utils` escribe como PARTSTAT).
"""

import json

_PARTSTAT = {"accepted": "ACCEPTED", "declined": "DECLINED", "tentative": "TENTATIVE"}


def _con_estado(attendees, email: str, partstat: str) -> list:
    if isinstance(attendees, str):
        attendees = json.loads(attendees or "[]")
    salida = []
    for a in attendees or []:
        if isinstance(a, str):
            a = {"email": a, "role": "REQ-PARTICIPANT"}
        if (a.get("email") or "").lower() == email.lower():
            a = {**a, "status": partstat}
        salida.append(a)
    return salida


async def propagar(db, uid: str, email: str, status: str) -> int:
    """Anota la respuesta de `email` en todas las copias del evento `uid`. Devuelve cuántas."""
    partstat = _PARTSTAT.get(status, "NEEDS-ACTION")
    filas = await db.fetch("SELECT id, attendees FROM events WHERE uid = $1", uid)
    for f in filas:
        await db.execute(
            """INSERT INTO event_invitations (event_id, attendee_email, status, responded_at)
               VALUES ($1, $2, $3, NOW())
               ON CONFLICT (event_id, attendee_email)
               DO UPDATE SET status = EXCLUDED.status, responded_at = NOW()""",
            f["id"],
            email,
            status,
        )
        await db.execute(
            "UPDATE events SET attendees = $1::jsonb, updated_at = now() WHERE id = $2",
            json.dumps(_con_estado(f["attendees"], email, partstat)),
            f["id"],
        )
    return len(filas)
