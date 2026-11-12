"""El «+» junto al remitente: completar, preguntar o no tocar el contacto que ya existe."""

from __future__ import annotations

import asyncio
import types

from app.contacts.routers import from_email
from app.contacts.services import alta_rapida as ar

CORREO = "ventas@example.org"


def test_el_correo_como_nombre_no_es_un_nombre_util():
    assert ar.nombre_util(CORREO, CORREO) == ""
    assert ar.nombre_util("ventas", CORREO) == ""
    assert ar.nombre_util("  ", CORREO) == ""
    assert ar.nombre_util('"Sofía  López"', CORREO) == "Sofía López"


def test_contacto_sin_nombre_se_completa():
    assert ar.decidir(CORREO, CORREO, "Sofía López") == "completar"
    assert ar.decidir("", CORREO, "Sofía López") == "completar"


def test_mismo_nombre_con_tildes_o_mayusculas_distintas_no_cambia_nada():
    assert ar.decidir("Sofia Lopez", CORREO, "SOFÍA LÓPEZ") == "igual"


def test_otro_nombre_se_pregunta_y_solo_cambia_con_confirmacion():
    assert ar.decidir("José Andrade", CORREO, "Sofía López") == "distinto"
    assert (
        ar.decidir("José Andrade", CORREO, "Sofía López", confirmado=True)
        == "actualizar"
    )


def test_si_el_correo_no_trae_nombre_no_se_borra_el_guardado():
    assert ar.decidir("José Andrade", CORREO, "") == "igual"
    assert ar.decidir("José Andrade", CORREO, CORREO, confirmado=True) == "igual"


def test_partir_nombre_y_apellido():
    assert ar.partir("Sofía López Mora") == ("Sofía", "López Mora")
    assert ar.partir("Sofía") == ("Sofía", "")


class _DB:
    def __init__(self, existente=None):
        self.existente, self.cambios = existente, []

    async def fetchrow(self, sql, *a):
        if sql.startswith("SELECT"):
            return self.existente
        self.cambios.append((sql, a))
        return {"id": 77}

    async def execute(self, sql, *a):
        self.cambios.append((sql, a))


def _pedir(db, cuerpo):
    async def json():
        return cuerpo

    req = types.SimpleNamespace(
        json=json, app=types.SimpleNamespace(state=types.SimpleNamespace(db_pool=db))
    )
    return asyncio.run(from_email.create_from_email(req, username="yo@example.org"))


def test_ruta_crea_con_nombre_y_apellido():
    db = _DB()
    r = _pedir(db, {"name": "Sofía López", "email": CORREO})
    assert r["status"] == "created" and db.cambios[0][1][1:4] == (
        "Sofía López",
        "Sofía",
        "López",
    )


def test_ruta_completa_el_contacto_importado_sin_nombre_y_el_autocompletado():
    db = _DB({"id": 5, "display_name": CORREO})
    r = _pedir(db, {"name": "Sofía López", "email": CORREO})
    assert r["status"] == "updated" and r["nombre"] == "Sofía López"
    assert any("UPDATE user_contacts" in s for s, _ in db.cambios)
    assert any("UPDATE sent_recipients" in s for s, _ in db.cambios)


def test_ruta_con_otro_nombre_pregunta_y_no_escribe():
    db = _DB({"id": 5, "display_name": "José Andrade"})
    r = _pedir(db, {"name": "Sofía López", "email": CORREO})
    assert r == {
        "status": "different",
        "id": 5,
        "nombre_guardado": "José Andrade",
        "nombre": "Sofía López",
    }
    assert db.cambios == []


def test_ruta_con_confirmacion_cambia_el_nombre():
    db = _DB({"id": 5, "display_name": "José Andrade"})
    r = _pedir(db, {"name": "Sofía López", "email": CORREO, "actualizar": True})
    assert r["status"] == "updated" and r["nombre_anterior"] == "José Andrade"


def test_ruta_mismo_nombre_responde_que_ya_existe():
    db = _DB({"id": 5, "display_name": "Sofia Lopez"})
    assert _pedir(db, {"name": "Sofía López", "email": CORREO})["status"] == "exists"
    assert db.cambios == []
