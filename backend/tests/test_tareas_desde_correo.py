"""Tareas al soltar correos en el ícono Tareas (06/11/2026).

- Una tarea por correo, en «Tareas», con el enlace al mensaje en task_correo_origen (no en task_correo,
  que es la de «Correo marcado» y movería la bandera).
- Un correo con tarea abierta no se repite; el mismo correo dos veces en un pedido cuenta una vez.
- Se limpian asunto y remitente; el pedido admite de 1 a 50 correos.
- Las vistas dan el enlace del correo soltado solo a quien lo soltó, con origen «soltado».
"""

import asyncio
import uuid

import pytest
from pydantic import ValidationError

from app.tasks import desde_correo, vistas
from app.tasks.service import task_service


class _Con:
    def __init__(self, abiertas=()):
        self.abiertas = set(abiertas)  # (carpeta, uid) con tarea abierta
        self.tarjetas, self.enlaces, self.sql = [], [], []

    async def execute(self, sql, *a):
        self.sql.append(sql)
        if "INSERT INTO task_correo_origen" in sql:
            self.enlaces.append(a)
        assert "INSERT INTO task_correo " not in sql

    async def fetchval(self, sql, *a):
        self.sql.append(sql)
        if "FROM task_correo_origen" in sql:
            return 1 if (a[1], a[2]) in self.abiertas else None
        if "COALESCE(MAX(position)" in sql:
            return len(self.tarjetas)
        if "INSERT INTO task_cards" in sql:
            self.tarjetas.append(a)
            return uuid.uuid4()
        raise AssertionError(sql)


@pytest.fixture(autouse=True)
def _lista(monkeypatch):
    async def lista(db, user):
        return "L1"

    async def tablero(db, list_id):
        return "B1"

    async def actividad(*a, **k):
        return None

    monkeypatch.setattr(task_service, "_get_default_list_id", lista)
    monkeypatch.setattr(task_service, "_get_board_id_for_list", tablero)
    monkeypatch.setattr(task_service, "_log_activity", actividad)


def _c(uid, asunto="Asunto", carpeta="INBOX", remitente="Ana Pérez <ana@x.org>"):
    return desde_correo.CorreoSoltado(
        carpeta=carpeta, uid=uid, asunto=asunto, remitente=remitente
    )


def test_una_tarea_por_correo_con_su_enlace():
    con = _Con()
    r = asyncio.run(
        desde_correo.crear(
            con, "yo@x.org", [_c(1, "Uno"), _c(2, "Dos", carpeta="Archivo")]
        )
    )
    assert len(r["creadas"]) == 2 and r["repetidas"] == 0
    assert [t[1] for t in con.tarjetas] == ["Uno", "Dos"]
    assert con.tarjetas[0][2] == "Creada desde el correo de Ana Pérez"
    assert [(e[2], e[3]) for e in con.enlaces] == [("INBOX", 1), ("Archivo", 2)]
    assert all(e[1] == "yo@x.org" for e in con.enlaces)


def test_no_repite_correos_con_tarea_abierta_ni_duplicados():
    con = _Con(abiertas={("INBOX", 1)})
    r = asyncio.run(desde_correo.crear(con, "yo@x.org", [_c(1), _c(2), _c(2)]))
    assert len(r["creadas"]) == 1 and r["repetidas"] == 1
    assert [(e[2], e[3]) for e in con.enlaces] == [("INBOX", 2)]


def test_sin_asunto_y_texto_limpio():
    con = _Con()
    c = desde_correo.CorreoSoltado(
        carpeta="INBOX", uid=5, asunto="  <b>x</b>  ", remitente="<i>Luis</i>"
    )
    assert c.asunto == "x" and "<" not in c.remitente
    asyncio.run(desde_correo.crear(con, "yo@x.org", [_c(6, asunto="")]))
    assert con.tarjetas[0][1] == "(sin asunto)"


def test_remitente_visible():
    f = desde_correo._remitente_visible
    assert f('"Ana" <ana@x.org>') == "Ana"
    assert f("<ana@x.org>") == "ana@x.org"
    assert f("") == "remitente desconocido"


def test_limites_del_pedido():
    with pytest.raises(ValidationError):
        desde_correo.PedidoDesdeCorreo(correos=[])
    with pytest.raises(ValidationError):
        desde_correo.PedidoDesdeCorreo(correos=[_c(i) for i in range(1, 52)])
    with pytest.raises(ValidationError):
        desde_correo.CorreoSoltado(carpeta="INBOX", uid=0)


def test_vistas_enlace_soltado_solo_de_quien_lo_solto():
    assert (
        "LEFT JOIN task_correo_origen cs ON cs.card_id = tc.id AND cs.user_email = $1"
        in (vistas._SELECT)
    )
    assert "'soltado'" in vistas._SELECT
