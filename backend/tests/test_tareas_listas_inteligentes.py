"""Listas inteligentes de Tareas al estilo To Do (F1, 29/10/2026).

- «Mi día» es de cada persona y de la fecha de hoy en Guayaquil: a medianoche queda vacío solo.
- «Asignado a mí» mira lo asignado en cualquier lista que la persona ve, sin lo de Seguimiento (T-34).
- «Correo marcado» se sincroniza con el buzón en los dos sentidos.
- Editar o borrar un paso exige ver la tarea (antes bastaba con conocer su id).
"""

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException

from app.tasks import correo_marcado, mi_dia
from app.tasks import router as tareas
from app.tasks import vistas


def test_mi_dia_usa_la_fecha_de_guayaquil():
    assert mi_dia.hoy() == datetime.now(ZoneInfo("America/Guayaquil")).date()


class _DBVista:
    def __init__(self):
        self.sql, self.args = "", ()

    async def fetch(self, sql, *args):
        self.sql, self.args = sql, args
        return []


@pytest.mark.parametrize(
    "nombre, fragmento",
    [
        ("my_day", "task_mi_dia"),
        ("important", "tc.important"),
        ("planned", "tc.reminder IS NOT NULL"),
        ("assigned", "NOT tc.asignada"),
        ("tasks", "list_type = 'default'"),
        ("flagged", "list_type = 'flagged'"),
    ],
)
def test_cada_vista_filtra_lo_suyo_sobre_las_listas_visibles(nombre, fragmento):
    db = _DBVista()
    assert asyncio.run(vistas.vista(db, "ana@example.org", nombre)) == []
    assert fragmento in db.sql
    assert "SELECT list_id FROM task_list_members WHERE user_email = $1" in db.sql
    assert db.args == ("ana@example.org", mi_dia.hoy())


def test_asignado_a_mi_mira_la_tabla_de_asignados():
    assert "task_asignados" in vistas.FILTROS["assigned"]


def test_vista_desconocida():
    with pytest.raises(ValueError):
        asyncio.run(vistas.vista(_DBVista(), "ana@example.org", "otra"))


def test_rutas_nuevas_publicadas():
    rutas = {(r.path, tuple(sorted(r.methods))) for r in tareas.router.routes}
    assert ("/views/tasks", ("GET",)) in rutas
    assert ("/lists/{list_id}/tasks", ("GET",)) in rutas
    assert ("/tasks/{card_id}/my-day", ("PATCH",)) in rutas


# ── Correo marcado ──


class _Con:
    """Conexión falsa: tareas del correo ya guardadas y registro de lo que se escribe."""

    def __init__(self, filas):
        self.filas, self.escrito = filas, []

    async def execute(self, sql, *args):
        self.escrito.append((" ".join(sql.split())[:40], args))

    async def fetch(self, sql, *args):
        return self.filas

    async def fetchval(self, sql, *args):
        if "RETURNING id" in sql:
            return "tarea-nueva"
        return 0


@pytest.fixture
def sin_tablero(monkeypatch):
    async def lista(db, user):
        return "lista-marcado", "tablero-1"

    async def actividad(*a, **k):
        return None

    monkeypatch.setattr(correo_marcado, "asegurar_lista", lista)
    monkeypatch.setattr(correo_marcado.task_service, "_log_activity", actividad)


def _hechos(con, inicio):
    return [e for e in con.escrito if e[0].startswith(inicio)]


def test_correo_marcado_nuevo_crea_su_tarea(sin_tablero):
    con = _Con([])
    m = [{"uid": 7, "message_id": "<a@x>", "subject": "Informe", "from": "Luis <l@x>"}]
    r = asyncio.run(correo_marcado.aplicar(con, "ana@example.org", m, True))
    assert r == {"creadas": 1, "reabiertas": 0, "completadas": 0}
    vinculo = _hechos(con, "INSERT INTO task_correo")[0][1]
    assert vinculo[:5] == ("tarea-nueva", "ana@example.org", "INBOX", 7, "<a@x>")


def test_quitar_la_bandera_completa_y_volver_a_marcar_reabre(sin_tablero):
    filas = [
        {
            "card_id": "t1",
            "message_id": "<a@x>",
            "uid": 7,
            "completed": False,
            "title": "A",
        },
        {
            "card_id": "t2",
            "message_id": "<b@x>",
            "uid": 8,
            "completed": True,
            "title": "B",
        },
    ]
    con = _Con(filas)
    m = [
        {"uid": 8, "message_id": "<b@x>", "subject": "B"}
    ]  # A perdió la bandera; B la recuperó
    r = asyncio.run(correo_marcado.aplicar(con, "ana@example.org", m, True))
    assert r == {"creadas": 0, "reabiertas": 1, "completadas": 1}


def test_si_la_lista_del_buzon_esta_incompleta_no_completa_nada(sin_tablero):
    filas = [
        {
            "card_id": "t1",
            "message_id": "<a@x>",
            "uid": 7,
            "completed": False,
            "title": "A",
        }
    ]
    con = _Con(filas)
    r = asyncio.run(correo_marcado.aplicar(con, "ana@example.org", [], False))
    assert r["completadas"] == 0


def test_correo_sin_message_id_se_reconoce_por_uid(sin_tablero):
    filas = [
        {"card_id": "t1", "message_id": "", "uid": 9, "completed": False, "title": "A"}
    ]
    con = _Con(filas)
    r = asyncio.run(
        correo_marcado.aplicar(
            con, "ana@example.org", [{"uid": 9, "subject": "A"}], True
        )
    )
    assert r == {"creadas": 0, "reabiertas": 0, "completadas": 0}


def test_completar_la_tarea_quita_la_bandera(monkeypatch):
    llamadas = []

    class _Imap:
        async def logout(self):
            pass

    async def conectar(request, user):
        return _Imap()

    async def banderas(imap, carpeta, uid, flags, add=True):
        llamadas.append((carpeta, uid, flags, add))
        return True

    class _Redis:
        async def delete(self, k):
            pass

    class _Req:
        class app:
            class state:
                redis = _Redis()

    import app.mail.clients.imap_client as imap_client

    monkeypatch.setattr(correo_marcado, "_conectar", conectar)
    monkeypatch.setattr(imap_client, "uid_set_flags", banderas)
    asyncio.run(
        correo_marcado.poner_bandera(
            _Req(), "ana@example.org", {"carpeta": "INBOX", "uid": 7}, False
        )
    )
    assert llamadas == [("INBOX", 7, "\\Flagged", False)]
    asyncio.run(correo_marcado.poner_bandera(_Req(), "ana@example.org", None, False))
    assert len(llamadas) == 1  # tarea que no viene del correo: no se toca el buzón


# ── Pasos ──


def test_editar_un_paso_ajeno_se_rechaza(monkeypatch):
    class _DB:
        async def fetchval(self, sql, *args):
            return "tarea-de-otro"

    async def no_ve(db, card_id, user):
        return False

    monkeypatch.setattr(tareas.acceso, "puede_ver_tarea", no_ve)
    with pytest.raises(HTTPException) as e:
        asyncio.run(tareas._verify_step_access(_DB(), "paso-1", "ana@example.org"))
    assert e.value.status_code == 403
