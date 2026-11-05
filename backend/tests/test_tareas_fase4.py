"""Fase 4 de la unificación (05/11/2026): aceptación implícita y correo de avisos según la preferencia."""

from __future__ import annotations

import asyncio
import uuid

from app.tareas import avisos, servicio

ID = uuid.uuid4()


class _DB:
    def __init__(self, quieren=()):
        self.quieren, self.sql = list(quieren), []

    async def execute(self, sql, *a):
        self.sql.append((sql, a))

    async def fetch(self, sql, *a):
        self.sql.append((sql, a))
        return [{"user_email": q} for q in self.quieren if q.lower() in a[0]]


def _row(aceptacion="sin_responder"):
    return {"id": ID, "aceptacion": aceptacion, "asignados": ["eva@example.org"]}


def test_empezar_o_completar_cuenta_como_aceptar():
    db = _DB()
    asyncio.run(servicio._aceptar_sin_pedirlo(db, _row(), "eva@example.org"))
    assert "aceptacion = 'aceptada'" in db.sql[0][0]
    # Una rechazada que se empieza también queda aceptada.
    db = _DB()
    asyncio.run(servicio._aceptar_sin_pedirlo(db, _row("rechazada"), "eva@example.org"))
    assert db.sql


def test_quien_asigno_no_acepta_por_otro_ni_se_repite():
    for row, quien in (
        (_row(), "ana@example.org"),
        (_row("aceptada"), "eva@example.org"),
    ):
        db = _DB()
        asyncio.run(servicio._aceptar_sin_pedirlo(db, row, quien))
        assert db.sql == []


def test_lo_importante_va_siempre_por_correo():
    for tipo in ("asignada", "activada", "vencida", "escalada"):
        assert asyncio.run(avisos._con_correo(_DB(), ["eva@example.org"], tipo)) == [
            "eva@example.org"
        ]


def test_lo_demas_solo_a_quien_quiere_correo():
    db = _DB(quieren=["Eva@example.org"])
    destinos = ["eva@example.org", "luis@example.org"]
    for tipo in ("completada", "comentario", "en_curso", "recordatorio_24h"):
        assert asyncio.run(avisos._con_correo(db, destinos, tipo)) == [
            "eva@example.org"
        ]


def test_sin_base_de_datos_como_antes():
    assert asyncio.run(avisos._con_correo(None, ["eva@example.org"], "comentario")) == [
        "eva@example.org"
    ]
