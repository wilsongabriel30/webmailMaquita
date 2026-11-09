"""Tareas: un solo tablero por persona (29/10/2026).

Al abrir Tareas llegan varias peticiones a la vez y todas pasan por ensure_default_board. Sin candado,
20 llamadas simultáneas creaban 10 tableros (probado contra PostgreSQL). Ahora:
- si el tablero y su lista «Tareas» ya existen, se devuelve sin transacción ni candado;
- si falta algo, se crea dentro de una transacción con un candado por persona.
"""

import asyncio
import uuid

from app.tasks import acceso
from app.tasks.service import task_service

TABLERO, LISTA = uuid.uuid4(), uuid.uuid4()


class _Transaccion:
    def __init__(self, con):
        self.con = con

    async def __aenter__(self):
        self.con.sql.append("BEGIN")

    async def __aexit__(self, *a):
        self.con.sql.append("COMMIT")


class _Con:
    """Conexión simulada: sin tableros hasta que se inserta uno."""

    def __init__(self, con_tablero=False):
        self.sql, self.tablero = [], con_tablero

    def transaction(self):
        return _Transaccion(self)

    async def fetchrow(self, sql, *a):
        self.sql.append(sql)
        if "list_id" in sql:
            return {"id": TABLERO, "list_id": LISTA} if self.tablero else None
        if "INSERT INTO task_boards" in sql:
            self.tablero = True
            return {"id": TABLERO}
        if "FROM task_boards" in sql:
            return {"id": TABLERO} if self.tablero else None
        return None

    async def fetchval(self, sql, *a):
        self.sql.append(sql)
        return LISTA

    async def execute(self, sql, *a):
        self.sql.append(sql)


def test_tablero_existente_sin_candado():
    con = _Con(con_tablero=True)
    assert asyncio.run(task_service.ensure_default_board(con, "ana@x.org")) == TABLERO
    assert con.sql and not any("advisory" in s or s == "BEGIN" for s in con.sql)


def test_persona_nueva_crea_con_candado(monkeypatch):
    async def _registrar(db, list_id, user):
        db.sql.append("registrar_propietaria")

    monkeypatch.setattr(acceso, "registrar_propietaria", _registrar)
    con = _Con()
    assert asyncio.run(task_service.ensure_default_board(con, "ana@x.org")) == TABLERO
    inicio, candado = con.sql.index("BEGIN"), next(
        i for i, s in enumerate(con.sql) if "pg_advisory_xact_lock" in s
    )
    alta = next(i for i, s in enumerate(con.sql) if "INSERT INTO task_boards" in s)
    assert inicio < candado < alta < con.sql.index("COMMIT")
    assert sum("INSERT INTO task_lists" in s for s in con.sql) == 1
