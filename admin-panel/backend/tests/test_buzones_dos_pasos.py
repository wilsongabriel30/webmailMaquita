"""Lista de buzones con la verificación en dos pasos: filtro, recuento y control de acceso.

La base simulada interpreta lo que la consulta pide (dominio, filtro «con»/«sin») sobre unas
cuentas de ejemplo, de modo que se comprueba el SQL generado y también el resultado."""

from datetime import date, datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_admin
from app.mailboxes import dos_pasos
from app.mailboxes.router import router as r_buzones

LECTOR = {
    "id": 2,
    "username": "lectura",
    "role": "viewer",
    "session_id": 1,
    "totp": False,
}
VERIFICADO = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)

# (dirección, activa, fila en user_totp: None = no tiene, False = empezada sin confirmar, True = activa)
CUENTAS = [
    ("admin@ejemplo.org", True, None),
    ("ana@ejemplo.org", True, True),
    ("luis@ejemplo.org", True, False),
    ("postmaster@ejemplo.org", True, True),
    ("baja@ejemplo.org", False, True),
    ("ana@otro.ejemplo.org", True, None),
    ("persona@otro.ejemplo.org", True, True),
]


def _fila(direccion, activa, totp, locales, direcciones):
    local, dominio = direccion.split("@")
    return {
        "username": direccion,
        "name": local.title(),
        "domain": dominio,
        "quota": 0,
        "active": activa,
        "local_part": local,
        "phone": "",
        "email_other": "",
        "created": VERIFICADO,
        "modified": VERIFICADO,
        "dos_pasos": totp is True,
        "dos_pasos_desde": VERIFICADO if totp is True else None,
        "dos_pasos_obligatoria": local in locales or direccion in direcciones,
    }


class BaseBuzones:
    def __init__(self, politica=(True, date(2027, 2, 28))):
        self.consultas = []
        self.politica = politica

    async def fetch(self, sql, *args):
        self.consultas.append((sql, args))
        assert "LEFT JOIN user_totp t ON t.username = m.username" in sql
        filas = [_fila(*c, args[0], args[1]) for c in CUENTAS]
        donde = sql.split("WHERE", 1)[1].split("ORDER BY")[0] if "WHERE" in sql else ""
        if "m.domain = $3" in donde:
            filas = [f for f in filas if f["domain"] == args[2]]
        if "NOT COALESCE(t.enabled, FALSE)" in donde:
            filas = [f for f in filas if not f["dos_pasos"]]
        elif "COALESCE(t.enabled, FALSE)" in donde:
            filas = [f for f in filas if f["dos_pasos"]]
        return filas

    async def fetchrow(self, sql, *args):
        self.consultas.append((sql, args))
        if "security_config" in sql:
            if self.politica is None:
                raise RuntimeError("no existe la tabla")
            return {"exigida": self.politica[0], "totp_deadline": self.politica[1]}
        activas = [_fila(*c, args[0], args[1]) for c in CUENTAS if c[1]]
        obligadas = [f for f in activas if f["dos_pasos_obligatoria"]]
        return {
            "cuentas_activas": len(activas),
            "con_dos_pasos": len([f for f in activas if f["dos_pasos"]]),
            "obligadas": len(obligadas),
            "obligadas_sin_activar": len([f for f in obligadas if not f["dos_pasos"]]),
        }


@pytest.fixture
def entorno(monkeypatch):
    monkeypatch.delenv("WEBMAIL_TOTP_OBLIGATORIO", raising=False)
    monkeypatch.delenv("TOTP_OBLIGATORIO", raising=False)
    app = FastAPI()
    app.include_router(r_buzones)
    app.include_router(dos_pasos.router)
    db = BaseBuzones()
    app.state.db = db
    app.dependency_overrides[get_current_admin] = lambda: LECTOR
    return TestClient(app), db, app


def _direcciones(respuesta):
    assert respuesta.status_code == 200
    return [f["username"] for f in respuesta.json()]


def test_sin_sesion_no_hay_lista_ni_recuento():
    app = FastAPI()
    app.include_router(r_buzones)
    app.include_router(dos_pasos.router)
    app.state.db = BaseBuzones()
    c = TestClient(app)
    assert c.get("/api/mailboxes").status_code == 401
    assert c.get("/api/mailboxes?dos_pasos=sin").status_code == 401
    assert c.get("/api/mailboxes/dos-pasos/resumen").status_code == 401


def test_la_lista_trae_el_estado_en_una_sola_consulta(entorno):
    c, db, _ = entorno
    filas = {f["username"]: f for f in c.get("/api/mailboxes").json()}
    assert len(filas) == len(CUENTAS) and len(db.consultas) == 1
    assert (
        filas["ana@ejemplo.org"]["dos_pasos"] is True
        and filas["ana@ejemplo.org"]["dos_pasos_desde"]
    )
    assert filas["admin@ejemplo.org"]["dos_pasos"] is False
    assert "password" not in filas["ana@ejemplo.org"]


def test_activacion_empezada_sin_confirmar_cuenta_como_sin_activar(entorno):
    c, _, _ = entorno
    luis = [
        f for f in c.get("/api/mailboxes").json() if f["username"] == "luis@ejemplo.org"
    ][0]
    assert luis["dos_pasos"] is False and luis["dos_pasos_desde"] is None
    assert "luis@ejemplo.org" in _direcciones(c.get("/api/mailboxes?dos_pasos=sin"))


def test_filtro_con_sus_tres_valores(entorno):
    c, _, _ = entorno
    todas = _direcciones(c.get("/api/mailboxes?dos_pasos=todas"))
    con = _direcciones(c.get("/api/mailboxes?dos_pasos=con"))
    sin = _direcciones(c.get("/api/mailboxes?dos_pasos=sin"))
    assert todas == _direcciones(c.get("/api/mailboxes"))
    assert con == [
        "ana@ejemplo.org",
        "postmaster@ejemplo.org",
        "baja@ejemplo.org",
        "persona@otro.ejemplo.org",
    ]
    assert sin == ["admin@ejemplo.org", "luis@ejemplo.org", "ana@otro.ejemplo.org"]
    assert sorted(con + sin) == sorted(todas)


def test_filtro_no_valido_se_rechaza_sin_consultar(entorno):
    c, db, _ = entorno
    r = c.get("/api/mailboxes?dos_pasos=quizas")
    assert r.status_code == 400 and "verificación en dos pasos" in r.json()["detail"]
    assert db.consultas == []


def test_filtro_combinado_con_el_dominio(entorno):
    c, db, _ = entorno
    assert _direcciones(
        c.get("/api/mailboxes?domain=otro.ejemplo.org&dos_pasos=con")
    ) == ["persona@otro.ejemplo.org"]
    assert _direcciones(
        c.get("/api/mailboxes?domain=otro.ejemplo.org&dos_pasos=sin")
    ) == ["ana@otro.ejemplo.org"]
    sql, args = db.consultas[-1]
    assert (
        "m.domain = $3 AND NOT COALESCE(t.enabled, FALSE)" in sql
        and args[2] == "otro.ejemplo.org"
    )
    assert sql.rstrip().endswith("ORDER BY m.username")


def test_los_valores_del_filtro_nunca_entran_en_la_consulta(entorno):
    c, db, _ = entorno
    c.get("/api/mailboxes?domain=x'%20OR%201=1--&dos_pasos=con")
    sql, args = db.consultas[-1]
    assert "OR 1=1" not in sql and args[2] == "x' OR 1=1--"


def test_cuentas_obligadas_segun_la_politica_del_webmail(entorno, monkeypatch):
    c, _, _ = entorno
    obligadas = lambda: sorted(
        f["username"]
        for f in c.get("/api/mailboxes").json()
        if f["dos_pasos_obligatoria"]
    )
    assert obligadas() == ["admin@ejemplo.org", "postmaster@ejemplo.org"]
    monkeypatch.setenv("TOTP_OBLIGATORIO", "Admin, persona@otro.ejemplo.org")
    assert obligadas() == ["admin@ejemplo.org", "persona@otro.ejemplo.org"]
    monkeypatch.setenv("WEBMAIL_TOTP_OBLIGATORIO", "")
    assert obligadas() == []


def test_reglas_obligatorias_separa_partes_locales_y_direcciones():
    assert dos_pasos.reglas_obligatorias("admin, Postmaster ,,soporte@ejemplo.org") == (
        ["admin", "postmaster"],
        ["soporte@ejemplo.org"],
    )
    assert dos_pasos.reglas_obligatorias("") == ([], [])


def test_recuento_sobre_cuentas_activas(entorno):
    c, _, _ = entorno
    r = c.get("/api/mailboxes/dos-pasos/resumen")
    assert r.status_code == 200
    assert r.json() == {
        "cuentas_activas": 6,
        "con_dos_pasos": 3,
        "sin_dos_pasos": 3,
        "obligadas": 2,
        "obligadas_sin_activar": 1,
        "exigida_a_todas": True,
        "fecha_limite": "2027-02-28",
    }


def test_recuento_sin_tabla_de_politicas(entorno):
    c, db, _ = entorno
    db.politica = None
    r = c.get("/api/mailboxes/dos-pasos/resumen").json()
    assert (
        r["exigida_a_todas"] is False
        and r["fecha_limite"] is None
        and r["cuentas_activas"] == 6
    )


def test_un_rol_de_solo_lectura_puede_consultar_pero_no_modificar(entorno):
    c, _, app = entorno
    assert c.get("/api/mailboxes?dos_pasos=con").status_code == 200
    assert c.get("/api/mailboxes/dos-pasos/resumen").status_code == 200
    del app.dependency_overrides[get_current_admin]
    assert c.post("/api/mailboxes/ana@ejemplo.org/toggle-active").status_code == 401
