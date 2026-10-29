"""Listas propias y grupos de Tareas al estilo To Do (F2, 29/10/2026).

- Nombre obligatorio y sin HTML; color #rrggbb; cinco órdenes posibles.
- Solo la propietaria cambia el nombre, el color o el ícono, o elimina la lista; el orden lo cambia
  cualquiera que la vea. «Tareas» no se renombra ni se elimina.
- El orden de la barra solo toca las listas y grupos de quien lo guarda.
"""

import asyncio
import uuid

import pytest
from pydantic import ValidationError

from app.tasks import listas
from app.tasks import router as tareas


def test_nombre_obligatorio_y_sin_html():
    assert listas.ListaNueva(name="  <b>Casa</b> ").name == "Casa"
    with pytest.raises(ValidationError):
        listas.ListaNueva(name="   ")
    with pytest.raises(ValidationError):
        listas.GrupoNuevo(name="<i></i>")


def test_color_y_orden_validos():
    assert listas.ListaNueva(name="x", color="#ABCDEF").color == "#abcdef"
    with pytest.raises(ValidationError):
        listas.ListaCambio(color="rojo")
    with pytest.raises(ValidationError):
        listas.ListaCambio(sort_by="aleatorio")
    for o in listas.ORDENES:
        assert listas.ListaCambio(sort_by=o).sort_by == o


def _lista(role="owner", list_type="custom"):
    return listas.Lista(
        id=uuid.uuid4(),
        board_id=uuid.uuid4(),
        name="Casa",
        position=0,
        color="#e0e0e0",
        list_type=list_type,
        role=role,
    )


class _DB:
    def __init__(self):
        self.sql = []

    async def execute(self, sql, *args):
        self.sql.append((sql, args))


@pytest.fixture
def lista_de(monkeypatch):
    def poner(lista):
        async def una(db, user, list_id):
            return lista

        monkeypatch.setattr(listas, "una_lista", una)

    return poner


def test_un_miembro_no_renombra_pero_si_ordena(lista_de):
    lista_de(_lista(role="member"))
    with pytest.raises(listas.SinPermiso):
        asyncio.run(
            listas.cambiar_lista(_DB(), "beto@x", "l1", listas.ListaCambio(name="Otra"))
        )
    db = _DB()
    asyncio.run(
        listas.cambiar_lista(db, "beto@x", "l1", listas.ListaCambio(sort_by="alpha"))
    )
    assert db.sql == [
        ("UPDATE task_lists SET sort_by = $2 WHERE id = $1", ("l1", "alpha"))
    ]


def test_un_miembro_no_elimina(lista_de):
    lista_de(_lista(role="member"))
    with pytest.raises(listas.SinPermiso):
        asyncio.run(listas.eliminar_lista(_DB(), "beto@x", "l1"))


def test_la_lista_tareas_no_se_renombra_ni_elimina(lista_de):
    lista_de(_lista(list_type="default"))
    with pytest.raises(ValueError):
        asyncio.run(
            listas.cambiar_lista(_DB(), "ana@x", "l1", listas.ListaCambio(name="Otra"))
        )
    with pytest.raises(ValueError):
        asyncio.run(listas.eliminar_lista(_DB(), "ana@x", "l1"))


def test_el_orden_de_la_barra_ignora_ids_ajenos():
    g, propia, ajena = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()

    class _Con(_DB):
        async def fetch(self, sql, *args):
            if "task_list_groups" in sql:
                return [{"id": g}]
            return [{"list_id": propia}]

    con = _Con()
    orden = listas.OrdenBarra(
        elementos=[
            {"tipo": "grupo", "id": g, "listas": [propia, ajena]},
            {"tipo": "lista", "id": ajena},
            {"tipo": "grupo", "id": uuid.uuid4()},
        ]
    )
    asyncio.run(listas.guardar_orden_barra(con, "ana@x", orden))
    args = [a for _, a in con.sql]
    assert args == [(g, 0), (propia, "ana@x", g, 0)]


def test_rutas_publicadas():
    rutas = {(r.path, m) for r in tareas.router.routes for m in r.methods}
    for ruta in [
        ("/lists", "GET"),
        ("/lists", "POST"),
        ("/lists/{list_id}", "PATCH"),
        ("/lists/{list_id}", "DELETE"),
        ("/lists/{list_id}/orden", "PUT"),
        ("/groups", "GET"),
        ("/groups", "POST"),
        ("/groups/{group_id}", "PATCH"),
        ("/groups/{group_id}", "DELETE"),
        ("/sidebar/orden", "PUT"),
    ]:
        assert ruta in rutas, ruta
