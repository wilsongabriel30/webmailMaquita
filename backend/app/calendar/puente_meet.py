# -*- coding: utf-8 -*-
"""
Puente calendario del correo → Maquita Meet (T-30). Módulo aparte del router/servicio del calendario.
- Evento creado con `meet: true` (la app o cualquier cliente de la API): crea la reunión en el servicio de reuniones
  (misma cuenta = moderador, asistentes = participantes → aviso T-03 + recordatorio), deja en el evento el enlace,
  «Entrar con tu usuario» y la marca X-MAQUITA-REUNION:<id>, y vincula la reunión con el evento.
- Evento editado o movido (arrastrar) con marca → actualiza la reunión (hora, asistentes, asunto).
  Evento borrado con marca → cancela la reunión.
El webmail (React) solo crea la reunión al guardar un evento nuevo; editar, mover y borrar los sincroniza
este módulo (una sola vez, sin avisos repetidos). Nunca rompe la operación del calendario.
"""

import logging
import math
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from app import organizacion
from app.calendar.schemas import EventUpdate

log = logging.getLogger(__name__)
CHAT = (
    organizacion.url_correo()
)  # mismo dominio: la cookie access_token del usuario vale para /api/chat
# «REUNION-ID» desde el 16/10/2026; «X-MAQUITA-REUNION» en los eventos anteriores (se siguen reconociendo).
MARCA = re.compile(r"(?:REUNION-ID|X-MAQUITA-REUNION):\s*(\d+)")


def _token(request):
    return request.cookies.get("access_token") if request is not None else None


def _horas(ev):
    """Horas enteras de la reunión, redondeadas hacia arriba (igual que el webmail: 90 min → 2 h)."""
    try:
        return max(1, math.ceil((ev.dtend - ev.dtstart).total_seconds() / 3600))
    except Exception:
        return 1


def _inicio_local(ev):
    """Hora de inicio en la zona del evento, sin zona: el servicio de reuniones guarda hora local.
    La BD devuelve `dtstart` en UTC; enviarlo tal cual dejaba la reunión 5 horas corrida.
    """
    inicio = ev.dtstart
    if inicio.tzinfo is not None:
        try:
            zona = ZoneInfo(getattr(ev, "timezone", None) or "America/Guayaquil")
        except Exception:
            zona = ZoneInfo("America/Guayaquil")
        inicio = inicio.astimezone(zona)
    return inicio.strftime("%Y-%m-%dT%H:%M")


def _asistentes(data_or_ev):
    lista = []
    for a in (getattr(data_or_ev, "attendees", None) or []) + (
        getattr(data_or_ev, "optional_attendees", None) or []
    ):
        lista.append(
            a if isinstance(a, str) else (a.get("email") if isinstance(a, dict) else "")
        )
    return [x for x in lista if x]


async def tras_crear(db, user, ev, data, request):
    if not getattr(data, "meet", False) or MARCA.search(ev.description or ""):
        return ev
    tok = _token(request)
    if not tok:
        return ev
    try:
        async with httpx.AsyncClient(timeout=30, cookies={"access_token": tok}) as c:
            r = await c.post(
                f"{CHAT}/api/chat/reuniones",
                json={
                    "asunto": ev.summary,
                    "inicio": _inicio_local(ev),
                    "duracion_horas": _horas(ev),
                    "participantes": _asistentes(data),
                    "calendario": False,
                },
            )
            reunion = (
                (r.json() or {}).get("reunion") if r.status_code in (200, 201) else None
            )
            if not reunion:
                log.warning(
                    "puente_meet: no se creó la reunión (%s %s)",
                    r.status_code,
                    r.text[:120],
                )
                return ev
            descripcion = (
                (ev.description + "\n\n" if ev.description else "")
                + f"Videollamada: {reunion['url_sala']}\nEntrar con tu usuario: {reunion['url_acceso']}?redirigir=1\nREUNION-ID: {reunion['id']}"
            )
            from app.calendar.service import calendar_service

            ev = await calendar_service.update_event(
                db,
                user,
                ev.id,
                EventUpdate(
                    description=descripcion, location=ev.location or reunion["url_sala"]
                ),
            )
            await c.post(
                f"{CHAT}/api/chat/reuniones/{reunion['id']}/vincular-evento",
                json={"evento_id": str(ev.id), "calendar_id": str(ev.calendar_id)},
            )
            ev = await calendar_service.get_event(
                db, user, ev.id
            )  # releído: trae reunion_id y meet_url
    except Exception as e:
        log.warning("puente_meet crear: %s", e)
    return ev


async def tras_actualizar(ev, request):
    m = MARCA.search(ev.description or "")
    tok = _token(request)
    if not m or not tok:
        return
    try:
        async with httpx.AsyncClient(timeout=20, cookies={"access_token": tok}) as c:
            await c.put(
                f"{CHAT}/api/chat/reuniones/{m.group(1)}",
                json={
                    "asunto": ev.summary,
                    "inicio": _inicio_local(ev),
                    "duracion_horas": _horas(ev),
                    "participantes": _asistentes(ev),
                    "sin_calendario": True,
                },
            )
    except Exception as e:
        log.warning("puente_meet actualizar: %s", e)


async def antes_de_eliminar(db, user, event_id):
    try:
        from app.calendar.service import calendar_service

        return await calendar_service.get_event(db, user, event_id)
    except Exception:
        return None


async def tras_eliminar(previo, request):
    m = MARCA.search((previo.description if previo else "") or "")
    tok = _token(request)
    if not m or not tok:
        return
    try:
        async with httpx.AsyncClient(timeout=20, cookies={"access_token": tok}) as c:
            await c.post(f"{CHAT}/api/chat/reuniones/{m.group(1)}/cancelar", json={})
    except Exception as e:
        log.warning("puente_meet cancelar: %s", e)
