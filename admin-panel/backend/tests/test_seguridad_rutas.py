"""Rutas de Seguridad → Tableros con una base simulada: permisos, validación y auditoría."""

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import require_operador, require_superadmin
from app.seguridad import router as r_tableros
from app.seguridad.router_alertas import router as r_alertas
from app.seguridad.router_informes import router as r_informes

ADMIN = {"id": 1, "username": "ana", "role": "superadmin", "session_id": 1, "totp": True}


class BaseFalsa:
    """Devuelve lo que se le prepare según un trozo de la consulta y apunta todo lo ejecutado."""

    def __init__(self):
        self.ejecutado = []
        self.filas: dict = {}
        self.fila: dict = {}

    def _buscar(self, tabla, sql, defecto):
        for clave, valor in tabla.items():
            if clave in sql:
                return valor
        return defecto

    async def fetch(self, sql, *args):
        self.ejecutado.append((sql, args))
        return self._buscar(self.filas, sql, [])

    async def fetchrow(self, sql, *args):
        self.ejecutado.append((sql, args))
        return self._buscar(self.fila, sql, None)

    async def fetchval(self, sql, *args):
        self.ejecutado.append((sql, args))
        return None

    async def execute(self, sql, *args):
        self.ejecutado.append((sql, args))
        return "UPDATE 1"

    def auditado(self, accion):
        return [a for s, a in self.ejecutado if "INSERT INTO admin_audit" in s and accion in a]


@pytest.fixture
def entorno():
    app = FastAPI()
    for r in (r_alertas, r_informes, r_tableros.router):
        app.include_router(r)
    db = BaseFalsa()
    app.state.db = db
    app.dependency_overrides[require_operador] = lambda: ADMIN
    app.dependency_overrides[require_superadmin] = lambda: ADMIN
    return TestClient(app), db, app


def test_sin_sesion_no_hay_tableros():
    app = FastAPI()
    app.include_router(r_tableros.router)
    app.state.db = BaseFalsa()
    c = TestClient(app)
    for ruta in ("/api/seguridad/resumen", "/api/seguridad/flujo", "/api/seguridad/wazuh"):
        assert c.get(ruta).status_code == 401


def test_fechas_no_validas(entorno):
    c, _, _ = entorno
    assert c.get("/api/seguridad/flujo?desde=2026-02-30").status_code == 400
    assert c.get("/api/seguridad/flujo?desde=2024-01-01&hasta=2026-10-01").status_code == 400
    assert c.get("/api/seguridad/flujo?agrupar=semana").status_code == 422
    assert c.get("/api/seguridad/accesos?servicio=telnet").status_code == 400


def test_flujo_vacio(entorno):
    c, _, _ = entorno
    r = c.get("/api/seguridad/flujo?desde=2026-10-01&hasta=2026-10-07")
    assert r.status_code == 200 and r.json()["serie"] == [] and r.json()["paso"] == "day"


def test_config_se_valida_y_se_audita(entorno):
    c, db, _ = entorno
    assert c.put("/api/seguridad/config", json={"retencion_dias": 5}).status_code == 400
    assert c.put("/api/seguridad/config", json={"zona_horaria": "Nada/Nada"}).status_code == 400
    r = c.put("/api/seguridad/config", json={"retencion_dias": 365, "umbral_fallos": 8})
    assert r.status_code == 200 and r.json()["retencion_dias"] == 365
    assert any("UPDATE seg_config" in s for s, _ in db.ejecutado)
    assert db.auditado("seguridad_config")


def test_reconocer_y_cerrar(entorno):
    c, db, _ = entorno
    assert c.post("/api/seguridad/alertas/9/reconocer", json={}).status_code == 409
    db.fila["SET estado = 'reconocida'"] = {"id": 9, "regla": "pais_nuevo", "cuenta": "ana@example.org", "ip": "198.51.100.7"}
    assert c.post("/api/seguridad/alertas/9/reconocer", json={"nota": "La llamo"}).status_code == 200
    assert db.auditado("seguridad_alerta_reconocer")
    assert c.post("/api/seguridad/alertas/9/cerrar", json={"resolucion": "falso_positivo", "nota": " "}).status_code == 400
    assert c.post("/api/seguridad/alertas/9/cerrar", json={"resolucion": "borrada"}).status_code == 422
    db.fila["SET estado = 'cerrada'"] = {"id": 9, "regla": "pais_nuevo", "cuenta": "ana@example.org", "ip": "198.51.100.7"}
    assert c.post("/api/seguridad/alertas/9/cerrar", json={"resolucion": "falso_positivo", "nota": "Viaje"}).status_code == 200
    assert db.auditado("seguridad_alerta_cerrar")
    assert c.get("/api/seguridad/alertas?estado=borradas").status_code == 422
    assert c.get("/api/seguridad/alertas?estado=pendientes").status_code == 200
    assert any("estado <> 'cerrada'" in s for s, _ in db.ejecutado)


def test_informes_csv_y_html(entorno):
    c, db, _ = entorno
    db.filas["FROM seg_accesos_detalle"] = [{"ip": "203.0.113.5", "pais": "RU", "fallos": 40, "ok": 0, "cuentas": 12,
                                             "servicios": ["imap"], "ultima": datetime(2026, 10, 20, tzinfo=timezone.utc)}]
    r = c.get("/api/seguridad/informes/ips.csv?desde=2026-10-14&hasta=2026-10-20")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert 'filename="seguridad-ips-20261014-20261020.csv"' in r.headers["content-disposition"]
    assert "203.0.113.5" in r.text and r.headers["cache-control"] == "no-store"
    assert db.auditado("seguridad_informe")
    assert c.get("/api/seguridad/informes/claves.csv").status_code == 422
    db.filas.clear()
    h = c.get("/api/seguridad/informes/resumen.html")
    assert h.status_code == 200 and "default-src 'none'" in h.headers["content-security-policy"]
    assert "Informe de seguridad del correo" in h.text


def test_wazuh_sin_agente(entorno, monkeypatch):
    c, _, _ = entorno
    from fastapi import HTTPException

    async def no_instalado(*a, **k):
        raise HTTPException(503, "Esta función no está instalada en el servidor")

    monkeypatch.setattr(r_tableros, "ayudante", no_instalado)
    assert c.get("/api/seguridad/wazuh").json() == {"instalado": False}

    async def conectado(cual, *args, **k):
        assert (cual, args) == ("wazuh", ("estado",))
        return {"instalado": True, "conectado": True, "manager": "siem.example.org"}

    monkeypatch.setattr(r_tableros, "ayudante", conectado)
    assert c.get("/api/seguridad/wazuh").json()["conectado"] is True
