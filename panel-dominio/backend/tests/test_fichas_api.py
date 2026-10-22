"""Fichas de API del portal (v1.11): alcance por método y ruta, creación solo con sesión y segundo factor, se
muestran una vez, se guardan con hash, se revocan y quedan en la auditoría. Con una base simulada."""

import hashlib
from datetime import datetime, timedelta, timezone

import pyotp
import pytest
from fastapi.testclient import TestClient

from app import fichas_alcance as fa
from app.main import app

SECRETO = pyotp.random_base32()


class Base:
    """Lo justo de asyncpg: una sesión, un administrador con segundo factor y la tabla de fichas."""

    def __init__(self):
        self.admin = {"id": 7, "username": "ana", "display_name": "Ana", "active": True, "must_change_password": False,
                      "totp_enabled": True, "totp_secret": SECRETO, "totp_last_step": 0}
        self.sesion = hashlib.sha256(b"sesion-de-pantalla-0123456789").hexdigest()
        self.fichas, self.auditoria = [], []

    def _ficha(self, token_hash):
        ahora = datetime.now(timezone.utc)
        return next((f for f in self.fichas if f["token_hash"] == token_hash and f["revoked_at"] is None
                     and f["expires_at"] > ahora), None)

    async def fetchrow(self, sql, *args):
        if "FROM pd_sesiones" in sql:
            if args[0] != self.sesion:
                return None
            return {"sesion_id": 1, **{k: self.admin[k] for k in ("id", "username", "display_name", "active",
                                                                   "must_change_password", "totp_enabled")}}
        if "FROM pd_fichas_api f JOIN pd_admins" in sql:
            f = self._ficha(args[0])
            return {"ficha_id": f["id"], "alcances": f["alcances"], **self.admin} if f else None
        if "SELECT totp_enabled, totp_secret" in sql:
            return self.admin
        raise AssertionError(sql)

    async def fetch(self, sql, *args):
        if "pd_admin_dominios" in sql:
            return [{"domain": "uno.example"}]
        if "FROM pd_fichas_api WHERE admin_id" in sql:
            return [{**f, "created_at": f["created_at"], "last_used_at": None} for f in self.fichas]
        return []

    async def fetchval(self, sql, *args):
        if sql.startswith("SELECT count(*) FROM pd_fichas_api"):
            return sum(1 for f in self.fichas if f["revoked_at"] is None)
        if "INSERT INTO pd_fichas_api" in sql:
            self.fichas.append({"id": len(self.fichas) + 1, "admin_id": args[0], "nombre": args[1], "prefijo": args[2],
                                "token_hash": args[3], "alcances": args[4], "expires_at": args[5], "revoked_at": None,
                                "created_at": datetime.now(timezone.utc)})
            return len(self.fichas)
        if sql.startswith("UPDATE pd_fichas_api SET revoked_at"):
            for f in self.fichas:
                if f["id"] == args[0] and f["admin_id"] == args[1] and f["revoked_at"] is None:
                    f["revoked_at"] = datetime.now(timezone.utc)
                    return f["id"]
            return None
        return None

    async def execute(self, sql, *args):
        if "pd_auditoria" in sql:
            self.auditoria.append(args)
        if "UPDATE pd_admins SET totp_last_step" in sql:
            self.admin["totp_last_step"] = args[1]


@pytest.fixture
def portal():
    base = Base()
    app.state.db = base
    return TestClient(app), base


SESION = {"Authorization": "Bearer sesion-de-pantalla-0123456789"}


def _codigo():
    return pyotp.TOTP(SECRETO).now()


def _crear(cliente, alcances=("lectura",), dias=30, **extra):
    return cliente.post("/api/fichas", headers=SESION, json={"nombre": "Integración", "alcances": list(alcances),
                                                             "dias": dias, "codigo": _codigo(), **extra})


# --- Alcance (sin base) ---


@pytest.mark.parametrize("alcances,metodo,ruta,esperado", [
    (["lectura"], "GET", "/api/cuentas", True),
    (["lectura"], "POST", "/api/cuentas", False),
    (["lectura"], "GET", "/api/sitios/uno.example/cortafuegos", True),
    (["lectura"], "PUT", "/api/sitios/uno.example/cortafuegos", False),
    (["sitios"], "PUT", "/api/sitios/uno.example/cortafuegos", True),
    (["sitios"], "POST", "/api/sitios/dns/uno.example", False),  # la zona DNS es otra área
    (["dns"], "POST", "/api/sitios/dns/uno.example", True),
    (["dns"], "GET", "/api/cuentas", False),
    (["lectura", "cuentas"], "DELETE", "/api/cuentas/ana@uno.example", True),
    (["lectura", "sitios", "dns", "cuentas", "alias", "reenvios", "grupos"], "POST", "/api/fichas", False),
    (["lectura", "sitios", "dns", "cuentas", "alias", "reenvios", "grupos"], "POST", "/api/acceso/clave", False),
    (["lectura", "sitios", "dns", "cuentas", "alias", "reenvios", "grupos"], "POST", "/api/acceso/totp/activar", False),
    (["lectura", "sitios", "dns", "cuentas", "alias", "reenvios", "grupos"], "POST", "/api/acceso/salir", False),
    (["lectura"], "GET", "/api/acceso/yo", True),
    (["lectura"], "GET", "/api/fichas", False),
    (["lectura"], "GET", "/api/marca", False),            # lo que no está en la lista: cerrado
    (["lectura"], "POST", "/api/resumen", False),
    (["sitios"], "GET", "/api/sitiosx", False),
    (["sitios"], "PUT", "/api/sitios/../cuentas", False),
    ("lectura", "GET", "/api/cuentas", False),
])
def test_alcance_por_metodo_y_ruta(alcances, metodo, ruta, esperado):
    assert fa.permitido(alcances, metodo, ruta) is esperado


def test_validar_alcances():
    assert fa.validar_alcances(["sitios", "lectura"]) == ["lectura", "sitios"]
    for malo in ([], ["todo"], ["lectura", "admin"], "lectura", None, [1]):
        assert fa.validar_alcances(malo) is None


# --- Crear, usar y revocar ---


def test_crear_se_muestra_una_vez_y_se_guarda_con_hash(portal):
    cliente, base = portal
    r = _crear(cliente)
    assert r.status_code == 201
    ficha = r.json()["ficha"]
    assert ficha.startswith("mqd_") and len(ficha) > 40
    guardada = base.fichas[0]
    assert guardada["token_hash"] == hashlib.sha256(ficha.encode()).hexdigest() and guardada["prefijo"] == ficha[:12]
    assert ficha not in str(base.fichas) and ficha not in str(base.auditoria)
    lista = cliente.get("/api/fichas", headers=SESION).json()
    assert "ficha" not in lista["fichas"][0] and lista["fichas"][0]["prefijo"] == ficha[:12]
    assert any(a[2] == "ficha_api_crear" for a in base.auditoria)


def test_crear_exige_codigo_del_segundo_factor(portal):
    cliente, base = portal
    r = cliente.post("/api/fichas", headers=SESION, json={"nombre": "x", "alcances": ["lectura"], "dias": 1})
    assert r.status_code == 400 and base.fichas == []
    codigo = _codigo()
    assert _crear(cliente, codigo=codigo).status_code == 201
    assert _crear(cliente, codigo=codigo).status_code == 400  # el mismo código no vale dos veces


@pytest.mark.parametrize("cuerpo", [
    {"nombre": "", "alcances": ["lectura"], "dias": 30}, {"nombre": "<script>", "alcances": ["lectura"], "dias": 30},
    {"nombre": "x", "alcances": ["todo"], "dias": 30}, {"nombre": "x", "alcances": [], "dias": 30},
    {"nombre": "x", "alcances": ["lectura"], "dias": 0}, {"nombre": "x", "alcances": ["lectura"], "dias": 366},
    {"nombre": "x", "alcances": ["lectura"], "dias": "30"}, {"nombre": "x", "alcances": ["lectura"]},
])
def test_crear_con_datos_no_validos(portal, cuerpo):
    cliente, base = portal
    assert cliente.post("/api/fichas", headers=SESION, json={**cuerpo, "codigo": _codigo()}).status_code == 400
    assert base.fichas == []


def test_usar_la_ficha_segun_su_alcance(portal):
    cliente, base = portal
    ficha = _crear(cliente).json()["ficha"]
    cabecera = {"Authorization": "Bearer " + ficha}
    assert cliente.get("/api/acceso/yo", headers=cabecera).json()["dominios"] == ["uno.example"]
    assert cliente.post("/api/cuentas", headers=cabecera, json={}).status_code == 403
    assert cliente.post("/api/fichas", headers=cabecera, json={"nombre": "otra", "alcances": ["lectura"], "dias": 1}).status_code == 403
    assert cliente.post("/api/acceso/clave", headers=cabecera, json={"actual": "x", "nueva": "y"}).status_code == 403
    assert cliente.get("/api/fichas", headers=cabecera).status_code == 403


def test_revocada_o_vencida_ya_no_vale(portal):
    cliente, base = portal
    ficha = _crear(cliente).json()["ficha"]
    cabecera = {"Authorization": "Bearer " + ficha}
    assert cliente.get("/api/acceso/yo", headers=cabecera).status_code == 200
    assert cliente.delete("/api/fichas/1", headers=SESION).status_code == 200
    assert cliente.get("/api/acceso/yo", headers=cabecera).status_code == 401
    assert cliente.delete("/api/fichas/1", headers=SESION).status_code == 404
    base.admin["totp_last_step"] = 0  # en la prueba, el mismo intervalo de 30 s: se olvida el código ya usado
    otra = _crear(cliente).json()["ficha"]
    base.fichas[-1]["expires_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert cliente.get("/api/acceso/yo", headers={"Authorization": "Bearer " + otra}).status_code == 401
    assert any(a[2] == "ficha_api_revocar" for a in base.auditoria)


def test_cuenta_desactivada_o_sin_segundo_factor(portal):
    cliente, base = portal
    cabecera = {"Authorization": "Bearer " + _crear(cliente).json()["ficha"]}
    base.admin["totp_enabled"] = False
    assert cliente.get("/api/acceso/yo", headers=cabecera).status_code == 403
    base.admin["totp_enabled"], base.admin["active"] = True, False
    assert cliente.get("/api/acceso/yo", headers=cabecera).status_code == 401


def test_maximo_de_fichas_activas(portal, monkeypatch):
    cliente, base = portal
    monkeypatch.setattr(fa, "MAXIMO_POR_CUENTA", 1)
    assert _crear(cliente).status_code == 201
    base.admin["totp_last_step"] = 0
    assert _crear(cliente).status_code == 409


def test_acciones_con_ficha_quedan_auditadas_con_su_numero(portal):
    from app.sesion import auditar

    class Peticion:
        headers = {}
        client = None
        app = type("A", (), {"state": type("S", (), {"db": portal[1]})})

    import asyncio

    asyncio.run(auditar(Peticion(), {"id": 7, "username": "ana", "ficha_api": 3}, "sitio_waf_guardar", "uno.example", {"modo": "detectar"}))
    assert '"ficha_api": 3' in portal[1].auditoria[-1][4]
