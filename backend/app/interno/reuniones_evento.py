"""Evento del calendario del correo de una reunión de Raíces (fase 2, 04/11/2026).

Alcance mínimo: solo se tocan eventos del calendario del ORGANIZADOR indicado que llevan la marca de esa
reunión (`REUNION-ID: <id>`, la antigua `X-MAQUITA-REUNION: <id>` o el enlace `/reuniones/<id>/acceso` que
ponía el servicio de reuniones). No se lee correo ni ningún otro evento.

- `sincronizar`: crea el evento si no existe; si existe, mueve hora/asunto/invitados. Idempotente: llamar
  dos veces no duplica y, si no cambió nada, no reenvía invitaciones.
- `cancelar`: borra el evento del organizador y las copias con el mismo UID que el calendario dejó a los
  invitados internos. Si ya no estaba, responde igual (0 eliminados).
"""

from __future__ import annotations

import json
import logging
import re
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app import organizacion
from app.calendar.schemas import EventCreate, EventUpdate
from app.calendar.service import calendar_service
from app.core.sanitize import strip_html

log = logging.getLogger("maquita.webmail.interno.reuniones")
ZONA = "America/Guayaquil"
_CANDADO_BASE = 0x5245_0000  # «RE»: espacio propio de candados de PostgreSQL


def patron_marca(reunion_id: int) -> str:
    """Expresión (PostgreSQL y Python) de las marcas que vinculan un evento con la reunión."""
    n = int(reunion_id)
    return rf"(REUNION-ID|X-MAQUITA-REUNION):\s*{n}([^0-9]|$)|/reuniones/{n}/acceso"


def tiene_marca(descripcion: str, reunion_id: int) -> bool:
    return re.search(patron_marca(reunion_id), descripcion or "") is not None


def inicio_con_zona(inicio: datetime) -> datetime:
    """Raíces guarda hora local de Ecuador sin zona; si viene con zona se respeta."""
    if inicio.tzinfo is None:
        return inicio.replace(tzinfo=ZoneInfo(ZONA))
    return inicio


def url_sala(sala: str) -> str:
    return f"{organizacion.url_reuniones().rstrip('/')}/{sala}"


def descripcion(reunion_id: int, sala: str, mensaje: str) -> str:
    acceso = f"{organizacion.url_correo().rstrip('/')}/api/chat/reuniones/{reunion_id}/acceso?redirigir=1"
    texto = strip_html(mensaje or "").strip()
    return (
        (texto + "\n\n" if texto else "")
        + f"Videollamada: {url_sala(sala)}\nEntrar con tu usuario: {acceso}\nREUNION-ID: {reunion_id}"
    )


def _correos(lista) -> list[str]:
    vistos: list[str] = []
    for a in lista or []:
        c = a if isinstance(a, str) else (a.get("email") if isinstance(a, dict) else "")
        c = (c or "").strip().lower()
        if c and c not in vistos:
            vistos.append(c)
    return vistos


async def es_buzon_activo(db, correo: str) -> bool:
    fila = await db.fetchval(
        "SELECT 1 FROM mailbox WHERE lower(username) = $1 AND active = TRUE", correo
    )
    return bool(fila)


@asynccontextmanager
async def candado(db, reunion_id: int):
    """Un solo cambio a la vez por reunión (evita duplicar si llegan dos creaciones juntas).
    Candado de TRANSACCIÓN (vale también con pgbouncer en modo «transaction»): se suelta solo al salir.
    """
    clave = _CANDADO_BASE + int(reunion_id)
    async with db.acquire() as con:
        async with con.transaction():
            await con.execute("SELECT pg_advisory_xact_lock($1)", clave)
            yield


async def eventos_de_la_reunion(db, organizador: str, reunion_id: int) -> list:
    return await db.fetch(
        """SELECT e.id, e.uid, e.calendar_id, e.summary, e.description, e.dtstart, e.dtend, e.attendees
           FROM events e JOIN calendars c ON c.id = e.calendar_id
           WHERE c.owner_email = $1 AND e.description ~ $2
           ORDER BY e.created_at NULLS LAST, e.id""",
        organizador,
        patron_marca(reunion_id),
    )


def _cambios(fila, asunto, ini, fin, participantes) -> EventUpdate | None:
    """None si el evento ya está igual (no se reescribe ni se reenvían invitaciones)."""
    actuales = fila["attendees"]
    if isinstance(actuales, str):
        actuales = json.loads(actuales or "[]")
    previos = sorted(_correos(actuales))
    mismos = (
        (fila["summary"] or "") == asunto
        and fila["dtstart"] == ini
        and fila["dtend"] == fin
        and previos == sorted(participantes)
    )
    if mismos:
        return None
    return EventUpdate(summary=asunto, dtstart=ini, dtend=fin, attendees=participantes)


async def sincronizar(
    db,
    *,
    reunion_id,
    organizador,
    asunto,
    inicio,
    duracion_horas,
    participantes,
    mensaje,
    sala,
) -> dict:
    ini = inicio_con_zona(inicio)
    fin = ini + timedelta(hours=duracion_horas)
    asunto = strip_html(asunto or "").strip()[:200] or "Reunión"
    invitados = [c for c in _correos(participantes) if c != organizador]
    async with candado(db, reunion_id):
        previos = await eventos_de_la_reunion(db, organizador, reunion_id)
        if previos:
            fila = previos[0]
            cambio = _cambios(fila, asunto, ini, fin, invitados)
            if cambio is not None:
                await calendar_service.update_event(db, organizador, fila["id"], cambio)
            return {
                "accion": "actualizado" if cambio is not None else "sin_cambios",
                "evento_id": str(fila["id"]),
                "calendar_id": str(fila["calendar_id"]),
            }
        cal = await calendar_service.ensure_default_calendar(db, organizador)
        ev = await calendar_service.create_event(
            db,
            organizador,
            EventCreate(
                calendar_id=cal.id,
                summary=asunto,
                description=descripcion(reunion_id, sala, mensaje),
                location=url_sala(sala),
                dtstart=ini,
                dtend=fin,
                timezone=ZONA,
                reminders=[{"minutes": 10}],
                attendees=invitados,
            ),
        )
        return {
            "accion": "creado",
            "evento_id": str(ev.id),
            "calendar_id": str(ev.calendar_id),
        }


async def cancelar(db, *, reunion_id, organizador) -> dict:
    eliminados, copias = 0, 0
    async with candado(db, reunion_id):
        for fila in await eventos_de_la_reunion(db, organizador, reunion_id):
            try:
                await calendar_service.delete_event(db, organizador, fila["id"])
                eliminados += 1
            except ValueError:
                continue  # ya no estaba: cancelar es idempotente
            borradas = await db.fetch(
                """DELETE FROM events e USING calendars c
                   WHERE c.id = e.calendar_id AND e.uid = $1 AND c.owner_email <> $2 AND e.description ~ $3
                   RETURNING e.id""",
                fila["uid"],
                organizador,
                patron_marca(reunion_id),
            )
            copias += len(borradas)
    return {
        "accion": "cancelado" if eliminados else "no_habia_evento",
        "eliminados": eliminados,
        "copias_invitados": copias,
    }
