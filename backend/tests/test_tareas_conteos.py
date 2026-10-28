"""Números de la barra lateral de Tareas (28/10/2026).

Antecedente: la barra lateral buscaba el total de cada vista en `/tasks/lists`, que solo trae listas
guardadas; las vistas (Mi día, Planeado…) salían sin número. `conteos.py` los cuenta en una consulta.
"""

import asyncio

from app.tasks import conteos
from app.tasks import router as tareas


class _DB:
    def __init__(self, fila):
        self.fila, self.sql, self.args = fila, "", ()

    async def fetchrow(self, sql, *args):
        self.sql, self.args = sql, args
        return self.fila


def test_cuenta_las_vistas_con_las_claves_del_frontend(monkeypatch):
    async def tablero(db, user):
        return "tablero-1"

    monkeypatch.setattr(conteos.task_service, "ensure_default_board", tablero)
    db = _DB({"mi_dia": 1, "importante": 0, "planeado": 2, "asignado": 0, "tareas": 3})
    r = asyncio.run(conteos.contar_vistas(db, "ana@example.org"))
    assert r == {"my-day": 1, "important": 0, "planned": 2, "assigned": 0, "tasks": 3}
    assert db.args == ("tablero-1", "ana@example.org")
    assert "tc.completed = FALSE" in db.sql  # solo pendientes, como Outlook


def test_las_rutas_de_conteo_estan_publicadas():
    rutas = {r.path for r in tareas.router.routes}
    assert "/views/counts" in rutas
    assert "/views/flagged/count" in rutas
