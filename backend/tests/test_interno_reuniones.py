"""Rutas internas Raíces → evento de la reunión en el calendario del correo (04/11/2026).

Acceso (token de servicio propio, IP de la conexión, sin cabeceras de reenvío del cliente),
alcance (solo eventos marcados de la reunión y del organizador) e idempotencia.
"""

import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.interno import reuniones_evento as rev
from app.interno.reuniones_router import router

TOKEN = "t" * 48
RAICES = "192.0.2.10"
ORG = "test@example.org"


class BaseFalsa:
    """Lo mínimo de asyncpg.Pool que usan las rutas, con eventos en memoria."""

    def __init__(self):
        self.eventos = (
            []
        )  # dicts con owner, id, uid, calendar_id, summary, description, dtstart, dtend, attendees
        self.buzones = {ORG, "test2@example.org"}
        self.candados = []

    async def fetchval(self, sql, correo):
        return 1 if correo in self.buzones else None

    async def fetch(self, sql, *args):
        if sql.lstrip().startswith("DELETE"):
            uid, org, patron = args
            borrar = [
                e
                for e in self.eventos
                if e["uid"] == uid
                and e["owner"] != org
                and re.search(patron, e["description"])
            ]
            self.eventos = [e for e in self.eventos if e not in borrar]
            return [{"id": e["id"]} for e in borrar]
        org, patron = args
        return [
            e
            for e in self.eventos
            if e["owner"] == org and re.search(patron, e["description"] or "")
        ]

    @asynccontextmanager
    async def acquire(self):
        yield SimpleNamespace(execute=self._execute, transaction=self._transaccion)

    @asynccontextmanager
    async def _transaccion(self):
        self.candados.append("BEGIN")
        yield
        self.candados.append("COMMIT")

    async def _execute(self, sql, clave):
        self.candados.append((sql.split("(")[0].split()[-1], clave))


@pytest.fixture
def entorno(monkeypatch):
    monkeypatch.setenv("REUNIONES_SERVICIO_TOKEN", TOKEN)
    monkeypatch.setenv("REUNIONES_SERVICIO_IPS", RAICES)
    monkeypatch.setenv("SECRET_KEY", "otro-secreto-de-sesiones")
    db = BaseFalsa()
    llamadas = {"crear": 0, "actualizar": 0, "borrar": 0}

    async def ensure_default_calendar(_db, user):
        return SimpleNamespace(id=uuid.UUID(int=1))

    async def create_event(_db, user, data):
        llamadas["crear"] += 1
        ev = {
            "owner": user,
            "id": uuid.uuid4(),
            "uid": "uid-1",
            "calendar_id": data.calendar_id,
            "summary": data.summary,
            "description": data.description,
            "dtstart": data.dtstart,
            "dtend": data.dtend,
            "attendees": [{"email": a} for a in data.attendees],
        }
        db.eventos.append(ev)
        return SimpleNamespace(id=ev["id"], calendar_id=ev["calendar_id"])

    async def update_event(_db, user, event_id, data):
        llamadas["actualizar"] += 1
        for e in db.eventos:
            if e["id"] == event_id and e["owner"] == user:
                e.update(
                    summary=data.summary,
                    dtstart=data.dtstart,
                    dtend=data.dtend,
                    attendees=[{"email": a} for a in data.attendees],
                )

    async def delete_event(_db, user, event_id):
        llamadas["borrar"] += 1
        antes = len(db.eventos)
        db.eventos = [
            e for e in db.eventos if not (e["id"] == event_id and e["owner"] == user)
        ]
        if len(db.eventos) == antes:
            raise ValueError("Event not found")

    for nombre, fn in (
        ("ensure_default_calendar", ensure_default_calendar),
        ("create_event", create_event),
        ("update_event", update_event),
        ("delete_event", delete_event),
    ):
        monkeypatch.setattr(rev.calendar_service, nombre, fn)
    app = FastAPI()
    app.include_router(router)
    app.state.db_pool = db
    return SimpleNamespace(app=app, db=db, llamadas=llamadas)


def _cliente(app, ip=RAICES):
    return AsyncClient(
        transport=ASGITransport(app=app, client=(ip, 40000)), base_url="http://test"
    )


def _cuerpo(**extra):
    d = {
        "reunion_id": 45,
        "organizador": "Test@Example.org ",
        "asunto": "Comité",
        "inicio": "2026-11-05T09:00",
        "duracion_horas": 1,
        "participantes": ["test2@example.org"],
        "mensaje": "Orden del día",
        "sala": "Comite-abc123",
    }
    d.update(extra)
    return d


AUT = {"Authorization": f"Bearer {TOKEN}"}


# ── Acceso ───────────────────────────────────────────────


async def test_sin_token_configurado_responde_503(entorno, monkeypatch):
    monkeypatch.delenv("REUNIONES_SERVICIO_TOKEN")
    async with _cliente(entorno.app) as c:
        r = await c.post("/api/interno/reuniones/evento", json=_cuerpo(), headers=AUT)
    assert r.status_code == 503


async def test_token_igual_al_secreto_de_sesiones_no_vale(entorno, monkeypatch):
    monkeypatch.setenv("SECRET_KEY", TOKEN)
    async with _cliente(entorno.app) as c:
        r = await c.post("/api/interno/reuniones/evento", json=_cuerpo(), headers=AUT)
    assert r.status_code == 503


async def test_token_corto_no_vale(entorno, monkeypatch):
    monkeypatch.setenv("REUNIONES_SERVICIO_TOKEN", "corto")
    async with _cliente(entorno.app) as c:
        r = await c.post(
            "/api/interno/reuniones/evento",
            json=_cuerpo(),
            headers={"Authorization": "Bearer corto"},
        )
    assert r.status_code == 503


async def test_token_equivocado_401(entorno):
    async with _cliente(entorno.app) as c:
        r = await c.post(
            "/api/interno/reuniones/evento",
            json=_cuerpo(),
            headers={"Authorization": "Bearer " + "x" * 48},
        )
        r2 = await c.post("/api/interno/reuniones/evento", json=_cuerpo())
    assert r.status_code == 401 and r2.status_code == 401
    assert entorno.llamadas["crear"] == 0


async def test_ip_no_permitida_403_aunque_el_token_sea_bueno(entorno):
    async with _cliente(entorno.app, ip="192.0.2.77") as c:
        r = await c.post("/api/interno/reuniones/evento", json=_cuerpo(), headers=AUT)
    assert r.status_code == 403


async def test_cabecera_de_reenvio_del_cliente_403(entorno):
    """Alguien que pase por el enrutador y mande X-Forwarded-For: 192.0.2.10 llega con dos saltos."""
    falsa = dict(AUT, **{"X-Forwarded-For": f"{RAICES}, {RAICES}"})
    otra = dict(AUT, **{"X-Real-IP": "192.0.2.99"})
    async with _cliente(entorno.app) as c:
        r = await c.post("/api/interno/reuniones/evento", json=_cuerpo(), headers=falsa)
        r2 = await c.post("/api/interno/reuniones/evento", json=_cuerpo(), headers=otra)
        r3 = await c.post(
            "/api/interno/reuniones/evento",
            json=_cuerpo(),
            headers=dict(AUT, **{"X-Forwarded-For": RAICES, "X-Real-IP": RAICES}),
        )
    assert r.status_code == 403 and r2.status_code == 403
    assert (
        r3.status_code == 200
    )  # lo que pone nginx para una conexión directa de Raíces


async def test_sin_autorizacion_no_se_valida_el_cuerpo(entorno):
    async with _cliente(entorno.app, ip="192.0.2.9") as c:
        r = await c.post("/api/interno/reuniones/evento", json={"basura": 1})
    assert r.status_code in (401, 403)


# ── Alcance ──────────────────────────────────────────────


async def test_organizador_sin_buzon_404(entorno):
    async with _cliente(entorno.app) as c:
        r = await c.post(
            "/api/interno/reuniones/evento",
            json=_cuerpo(organizador="nadie@example.org"),
            headers=AUT,
        )
    assert r.status_code == 404
    assert entorno.llamadas["crear"] == 0


async def test_campos_extra_y_sala_rara_se_rechazan(entorno):
    async with _cliente(entorno.app) as c:
        r = await c.post(
            "/api/interno/reuniones/evento",
            json=_cuerpo(evento_id="cualquiera"),
            headers=AUT,
        )
        r2 = await c.post(
            "/api/interno/reuniones/evento", json=_cuerpo(sala="../x?y"), headers=AUT
        )
    assert r.status_code == 422 and r2.status_code == 422


def test_marca_exacta_de_la_reunion():
    p = rev.patron_marca(45)
    assert re.search(p, "x\nREUNION-ID: 45")
    assert re.search(p, "X-MAQUITA-REUNION:45\n")
    assert re.search(
        p, "Entrar: https://mail.example.org/api/chat/reuniones/45/acceso?redirigir=1"
    )
    assert not re.search(p, "REUNION-ID: 453")
    assert not re.search(p, "/reuniones/450/acceso")
    assert not re.search(p, "sin marca")


async def test_no_toca_eventos_de_otra_reunion_ni_de_otro_dueno(entorno):
    ajeno = {
        "owner": "otro@example.org",
        "id": uuid.uuid4(),
        "uid": "u-x",
        "calendar_id": uuid.UUID(int=9),
        "summary": "Ajena",
        "description": "REUNION-ID: 45",
        "dtstart": None,
        "dtend": None,
        "attendees": [],
    }
    otra = dict(ajeno, owner=ORG, id=uuid.uuid4(), description="REUNION-ID: 453")
    entorno.db.eventos += [ajeno, otra]
    async with _cliente(entorno.app) as c:
        r = await c.post(
            "/api/interno/reuniones/evento/cancelar",
            json={"reunion_id": 45, "organizador": ORG},
            headers=AUT,
        )
    assert r.json()["accion"] == "no_habia_evento"
    assert ajeno in entorno.db.eventos and otra in entorno.db.eventos


# ── Crear / actualizar / cancelar ────────────────────────


async def test_crear_es_idempotente_y_actualizar_mueve(entorno):
    async with _cliente(entorno.app) as c:
        r1 = await c.post("/api/interno/reuniones/evento", json=_cuerpo(), headers=AUT)
        r2 = await c.post("/api/interno/reuniones/evento", json=_cuerpo(), headers=AUT)
        r3 = await c.post(
            "/api/interno/reuniones/evento",
            json=_cuerpo(inicio="2026-11-05T10:30", duracion_horas=2),
            headers=AUT,
        )
    assert r1.json()["accion"] == "creado"
    assert r2.json()["accion"] == "sin_cambios"
    assert r3.json()["accion"] == "actualizado"
    assert r1.json()["evento_id"] == r2.json()["evento_id"] == r3.json()["evento_id"]
    assert entorno.llamadas == {"crear": 1, "actualizar": 1, "borrar": 0}
    ev = entorno.db.eventos[0]
    assert ev["owner"] == ORG
    assert ev["dtstart"].astimezone(timezone.utc) == datetime(
        2026, 11, 5, 15, 30, tzinfo=timezone.utc
    )
    assert ev["dtend"] - ev["dtstart"] == timedelta(hours=2)
    assert (
        "REUNION-ID: 45" in ev["description"] and "Videollamada: " in ev["description"]
    )
    assert "/api/chat/reuniones/45/acceso?redirigir=1" in ev["description"]
    assert entorno.db.candados[:3] == [
        "BEGIN",
        ("pg_advisory_xact_lock", rev._CANDADO_BASE + 45),
        "COMMIT",
    ]


async def test_el_organizador_no_queda_como_invitado(entorno):
    async with _cliente(entorno.app) as c:
        await c.post(
            "/api/interno/reuniones/evento",
            json=_cuerpo(participantes=[ORG, "TEST2@example.org"]),
            headers=AUT,
        )
    assert entorno.db.eventos[0]["attendees"] == [{"email": "test2@example.org"}]


async def test_cancelar_quita_el_evento_y_las_copias_y_es_idempotente(entorno):
    async with _cliente(entorno.app) as c:
        await c.post("/api/interno/reuniones/evento", json=_cuerpo(), headers=AUT)
        copia = dict(entorno.db.eventos[0], owner="test2@example.org", id=uuid.uuid4())
        entorno.db.eventos.append(copia)
        r1 = await c.post(
            "/api/interno/reuniones/evento/cancelar",
            json={"reunion_id": 45, "organizador": ORG},
            headers=AUT,
        )
        r2 = await c.post(
            "/api/interno/reuniones/evento/cancelar",
            json={"reunion_id": 45, "organizador": ORG},
            headers=AUT,
        )
    assert (
        r1.status_code == 200
        and r1.json()["eliminados"] == 1
        and r1.json()["copias_invitados"] == 1
    )
    assert r2.status_code == 200 and r2.json()["accion"] == "no_habia_evento"
    assert entorno.db.eventos == []
