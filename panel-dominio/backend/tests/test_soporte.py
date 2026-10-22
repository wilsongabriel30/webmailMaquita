"""Entrada de soporte «como el cliente»: canje del vale, solo lectura en TODAS las rutas que modifican,
nada de tocar la clave ni el segundo factor del cliente y auditoría con la marca de soporte."""

import json
import re
from datetime import datetime, timedelta, timezone

import asyncpg
import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app import sesion_soporte
from app.main import app

FICHA = "ficha-de-soporte-0123456789abcdef"
CABECERA = {"Authorization": "Bearer " + FICHA}
VALE = "v" * 43
ESCRITURA = {"POST", "PUT", "PATCH", "DELETE"}
# Rutas que modifican y no piden sesión: entrar y canjear el vale de soporte.
SIN_SESION = {"/api/acceso/entrar", "/api/acceso/soporte"}


class BaseSoporte:
    """Doble de la base: ninguna sesión de administrador, una de soporte de uno.example."""

    def __init__(self, solo_lectura=True, vale=True, tabla=True):
        self.solo_lectura, self.vale, self.tabla = solo_lectura, vale, tabla
        self.ejecutadas: list[tuple] = []
        self.vence = datetime.now(timezone.utc) + timedelta(minutes=60)

    def _sin_tabla(self):
        if not self.tabla:
            raise asyncpg.exceptions.UndefinedTableError("no existe la relación")

    async def fetchrow(self, sql, *args):
        if "FROM pd_sesiones s JOIN pd_admins" in sql:
            return None
        if "FROM pd_sesiones_soporte" in sql:
            self._sin_tabla()
            return {"id": 9, "domain": "uno.example", "superadmin": "admin", "solo_lectura": self.solo_lectura,
                    "expires_at": self.vence}
        if "UPDATE pd_vales_soporte" in sql:
            self._sin_tabla()
            self.ejecutadas.append(("canje", args))
            return {"id": 4, "domain": "uno.example", "superadmin": "admin", "solo_lectura": self.solo_lectura,
                    "origen": "panel", "motivo": "incidencia 12"} if self.vale else None
        raise AssertionError(f"consulta inesperada: {sql}")

    async def fetchval(self, sql, *args):
        if "INSERT INTO pd_sesiones_soporte" in sql:
            self.ejecutadas.append(("sesion", args))
            return 9
        raise AssertionError(f"consulta inesperada: {sql}")

    async def fetch(self, sql, *args):
        raise AssertionError(f"en solo lectura no se llega a consultar: {sql}")

    async def execute(self, sql, *args):
        self.ejecutadas.append((sql, args))
        return "OK"

    def auditoria(self):
        return [a for s, a in self.ejecutadas if isinstance(s, str) and "pd_auditoria" in s]


@pytest.fixture
def cliente():
    def crear(**kw):
        base = BaseSoporte(**kw)
        app.state.db = base
        return TestClient(app), base
    return crear


def _ruta_de_prueba(ruta: str) -> str:
    return re.sub(r"\{[^}]+\}", "uno.example", ruta)


RUTAS_ESCRITURA = sorted(
    (metodo, r.path) for r in app.routes if isinstance(r, APIRoute) for metodo in r.methods & ESCRITURA
)


def test_hay_rutas_que_probar():
    assert len(RUTAS_ESCRITURA) > 40
    assert ("POST", "/api/acceso/salir") in RUTAS_ESCRITURA


@pytest.mark.parametrize("metodo,ruta", RUTAS_ESCRITURA)
def test_solo_lectura_rechaza_toda_peticion_que_modifica(cliente, metodo, ruta):
    if ruta in SIN_SESION or ruta == "/api/acceso/salir":
        pytest.skip("sin sesión, o cerrar la sesión (permitido)")
    c, base = cliente()
    r = c.request(metodo, _ruta_de_prueba(ruta), headers=CABECERA, json={})
    assert r.status_code == 403, (metodo, ruta, r.text)
    assert not base.auditoria()


def test_solo_lectura_deja_cerrar_la_sesion(cliente):
    c, base = cliente()
    assert c.post("/api/acceso/salir", headers=CABECERA).status_code == 200
    assert any("UPDATE pd_sesiones_soporte SET revoked_at" in s for s, _ in base.ejecutadas if isinstance(s, str))


def test_yo_dice_que_es_soporte(cliente):
    c, _ = cliente()
    r = c.get("/api/acceso/yo", headers=CABECERA)
    assert r.status_code == 200
    datos = r.json()
    assert datos["dominios"] == ["uno.example"]
    assert datos["soporte"]["solo_lectura"] is True and datos["soporte"]["superadmin"] == "admin"
    assert datos["debe_cambiar_clave"] is False and datos["debe_activar_segundo_factor"] is False


@pytest.mark.parametrize("ruta", ["/api/acceso/clave", "/api/acceso/totp/iniciar", "/api/acceso/totp/activar"])
def test_ni_con_acciones_se_toca_la_clave_ni_el_segundo_factor(cliente, ruta):
    c, _ = cliente(solo_lectura=False)
    assert c.post(ruta, headers=CABECERA, json={}).status_code == 403
    assert c.get("/api/acceso/totp/estado", headers=CABECERA).status_code == 403


class _Peticion:
    def __init__(self, metodo, ruta):
        self.method = metodo

        class U:
            path = ruta

        self.url = U()


def test_con_acciones_se_permite_modificar():
    admin = sesion_soporte.como_admin(9, "uno.example", "admin", False, "2026-10-21T10:00:00+00:00")
    sesion_soporte.exigir_permitido(_Peticion("POST", "/api/cuentas"), admin)  # no lanza
    sesion_soporte.exigir_permitido(_Peticion("DELETE", "/api/alias/a@uno.example"), admin)


def test_las_acciones_quedan_con_la_marca_de_soporte():
    admin = sesion_soporte.como_admin(9, "uno.example", "admin", False, "x")
    marcado = sesion_soporte.marcar(admin, {"cuenta": "ana@uno.example"})
    assert marcado == {"cuenta": "ana@uno.example", "soporte": {"superadmin": "admin", "modo": "con_acciones"}}
    assert sesion_soporte.marcar({"username": "ana"}, None) is None
    assert admin["username"] == "soporte:admin" and admin["id"] is None


def test_canje_abre_la_sesion_y_lo_audita(cliente):
    c, base = cliente()
    r = c.post("/api/acceso/soporte", json={"vale": VALE})
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["dominio"] == "uno.example" and datos["soporte"]["modo"] == "solo_lectura"
    assert len(datos["token"]) >= 40
    canje = next(a for s, a in base.ejecutadas if s == "canje")
    assert canje[0] != VALE and len(canje[0]) == 64  # se busca por hash, nunca en claro
    sesion = next(a for s, a in base.ejecutadas if s == "sesion")
    assert datos["token"] not in sesion  # la ficha se guarda como hash
    vence = sesion[-1]
    assert timedelta(minutes=4) < vence - datetime.now(timezone.utc) <= timedelta(minutes=sesion_soporte.MINUTOS_SOPORTE)
    (auditoria,) = base.auditoria()
    assert auditoria[1] == "soporte:admin" and auditoria[2] == "soporte_entrada" and auditoria[3] == "uno.example"
    detalles = json.loads(auditoria[4])
    assert detalles["texto"] == "el superadmin admin entró como soporte de uno.example"
    assert detalles["soporte"] == {"superadmin": "admin", "modo": "solo_lectura"}


@pytest.mark.parametrize("vale", ["", "corto", "x" * 200, "con espacios " * 4, "a'; DROP TABLE x; --" * 3, None, 7])
def test_vale_con_forma_invalida_ni_se_busca(cliente, vale):
    c, base = cliente()
    assert c.post("/api/acceso/soporte", json={"vale": vale}).status_code == 401
    assert base.ejecutadas == []


def test_vale_usado_o_caducado(cliente):
    c, base = cliente(vale=False)
    assert c.post("/api/acceso/soporte", json={"vale": VALE}).status_code == 401
    assert not any(s == "sesion" for s, _ in base.ejecutadas)


def test_sin_tablas_de_soporte(cliente):
    c, _ = cliente(tabla=False)
    assert c.post("/api/acceso/soporte", json={"vale": VALE}).status_code == 503
    # Y una ficha cualquiera sigue sin valer (no rompe las sesiones normales).
    assert c.get("/api/acceso/yo", headers=CABECERA).status_code == 401


def test_minutos_de_soporte_acotados(monkeypatch):
    for valor, esperado in (("60", 60), ("1", 5), ("100000", 240), ("no", 60)):
        monkeypatch.setenv("PD_MINUTOS_SOPORTE", valor)
        assert sesion_soporte._minutos() == esperado
