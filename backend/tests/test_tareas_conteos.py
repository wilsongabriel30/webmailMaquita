"""Números de la barra lateral de Tareas (28/10/2026; F1 To Do 29/10/2026).

Antecedente: la barra lateral buscaba el total de cada vista en `/tasks/lists`, que solo trae listas
guardadas; las vistas (Mi día, Planeado…) salían sin número. Ahora los cuenta `vistas.contar` en una
consulta, sobre las listas que la persona ve (propias y compartidas) y con su «Mi día» de hoy.
"""

import asyncio

from app.tasks import mi_dia
from app.tasks import router as tareas
from app.tasks import vistas


class _DB:
    def __init__(self, fila):
        self.fila, self.sql, self.args = fila, "", ()

    async def fetchrow(self, sql, *args):
        self.sql, self.args = sql, args
        return self.fila


def test_cuenta_las_vistas_con_las_claves_del_frontend():
    db = _DB(
        {
            "mi_dia": 1,
            "importante": 0,
            "planeado": 2,
            "asignado": 0,
            "tareas": 3,
            "marcado": 4,
        }
    )
    r = asyncio.run(vistas.contar(db, "ana@example.org"))
    assert r == {
        "my-day": 1,
        "important": 0,
        "planned": 2,
        "assigned": 0,
        "tasks": 3,
        "flagged": 4,
    }
    assert db.args == ("ana@example.org", mi_dia.hoy())
    assert "tc.completed = FALSE" in db.sql  # solo pendientes, como Outlook
    assert "task_list_members" in db.sql  # también las listas compartidas


def test_las_rutas_de_conteo_estan_publicadas():
    rutas = {r.path for r in tareas.router.routes}
    assert "/views/counts" in rutas
    assert "/views/flagged/count" in rutas
