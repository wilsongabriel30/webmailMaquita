"""Auditoría y estado del túnel de soporte, y retirada de la clave privada de la carga guardada."""

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest
from dobles_flota import ADMIN, EQUIPO, BaseFalsa, leer_carga
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import require_operador
from app.flota import cargas, tunel_estado, tunel_purga
from app.flota.router_ordenes import router as r_ordenes
from app.flota.router_tunel import router as r_tunel

AHORA = datetime(2026, 11, 13, 21, 0, tzinfo=timezone.utc)
PLANOS = {
    "host": "tuneles.example.org",
    "puerto_ssh": 443,
    "usuario": "tunel",
    "puerto_remoto": 22002,
    "minutos": 30,
}


def fila(**cambios):
    base = {
        "orden_id": "o1",
        "equipo_id": EQUIPO,
        "nombre": "EQUIPO-DE-PRUEBA",
        "parametros": dict(PLANOS),
        "estado": "ok",
        "motivo": "Soporte remoto",
        "emitida_por": "ana",
        "emitida_en": AHORA - timedelta(minutes=20),
        "resultado_en": AHORA - timedelta(minutes=10),
        "datos": None,
        "caducada": False,
        "cierre_estado": None,
        "cierre_en": None,
        "reemplazado_en": None,
    }
    return {**base, **cambios}


def test_abierto_con_cuenta_atras_segun_el_equipo():
    expira = AHORA + timedelta(minutes=19)
    r = tunel_estado.resumir(fila(datos={"expira_en": expira.isoformat()}), AHORA)
    assert (r["situacion"], r["expira_en"], r["duracion_s"], r["cerrado_en"]) == (
        "abierto",
        expira,
        600,
        None,
    )


def test_sin_dato_del_equipo_se_calcula_con_los_minutos():
    for datos in (
        None,
        {},
        {"expira_en": "16:53"},
        {"expira_en": "2020-01-01T00:00:00Z"},
        {"expira_en": 5},
    ):
        r = tunel_estado.resumir(fila(datos=datos), AHORA)
        assert (
            r["expira_en"] == AHORA + timedelta(minutes=20)
            and r["situacion"] == "abierto"
        )


def test_cierre_automatico_por_orden_y_por_nueva_apertura():
    abierto = AHORA - timedelta(minutes=50)
    r = tunel_estado.resumir(fila(resultado_en=abierto), AHORA)
    assert (r["situacion"], r["cierre"], r["duracion_s"]) == (
        "cerrado",
        "automático",
        1800,
    )
    r = tunel_estado.resumir(
        fila(cierre_estado="ok", cierre_en=AHORA - timedelta(minutes=4)), AHORA
    )
    assert (r["situacion"], r["cierre"], r["duracion_s"]) == (
        "cerrado",
        "orden de cierre",
        360,
    )
    r = tunel_estado.resumir(fila(reemplazado_en=AHORA - timedelta(minutes=8)), AHORA)
    assert (r["situacion"], r["cierre"], r["duracion_s"]) == (
        "cerrado",
        "nueva apertura",
        120,
    )
    r = tunel_estado.resumir(fila(cierre_estado="pendiente"), AHORA)
    assert r["situacion"] == "cierre_solicitado"


@pytest.mark.parametrize(
    "cambios, situacion",
    [
        ({"estado": "pendiente", "resultado_en": None}, "solicitado"),
        ({"estado": "entregada", "resultado_en": None}, "solicitado"),
        ({"estado": "entregada", "resultado_en": None, "caducada": True}, "caducada"),
        ({"estado": "ejecutando"}, "abriendo"),
        ({"estado": "error"}, "no_abierto"),
        ({"estado": "rechazada"}, "no_abierto"),
        ({"estado": "anulada", "resultado_en": None}, "no_abierto"),
    ],
)
def test_situaciones_sin_tunel(cambios, situacion):
    r = tunel_estado.resumir(fila(**cambios), AHORA)
    assert (
        r["situacion"] == situacion
        and r["duracion_s"] is None
        and r["abierto_en"] is None
    )


@pytest.fixture
def entorno():
    app = FastAPI()
    app.include_router(r_tunel)
    app.include_router(r_ordenes)
    db = BaseFalsa()
    app.state.db = db
    app.dependency_overrides[require_operador] = lambda: ADMIN
    return TestClient(app), db


def test_auditoria_dice_quien_a_que_equipo_cuando_resultado_y_duracion(entorno):
    c, db = entorno
    ahora = datetime.now(timezone.utc)
    db.filas["LEFT JOIN LATERAL"] = [
        fila(
            parametros=json.dumps({**PLANOS, "clave_en_orden": False}),
            emitida_en=ahora - timedelta(hours=2),
            resultado_en=ahora - timedelta(hours=1),
            ip_panel="192.0.2.7",
        )
    ]
    r = c.get("/api/flota/tunel/auditoria")
    assert r.status_code == 200
    (t,) = r.json()["tuneles"]
    assert (
        t["emitida_por"],
        t["nombre"],
        t["situacion"],
        t["cierre"],
        t["duracion_s"],
    ) == ("ana", "EQUIPO-DE-PRUEBA", "cerrado", "automático", 1800)
    assert t["parametros"]["puerto_remoto"] == 22002 and t["ip_panel"] == "192.0.2.7"
    sql = db.con("LEFT JOIN LATERAL")
    assert sql and "carga" not in next(
        s for s, _ in db.ejecutado if "LEFT JOIN LATERAL" in s
    ).replace("carga,", "")
    assert c.get("/api/flota/tunel/auditoria?equipo_id=no-es-uuid").status_code == 400


def test_estado_de_un_equipo_con_puerto_asignado_o_sugerido(entorno):
    c, db = entorno
    r = c.get(f"/api/flota/tunel/estado?equipo_id={EQUIPO}")
    assert r.status_code == 200
    assert (
        r.json()["tunel"] is None
        and r.json()["puerto_asignado"] is None
        and r.json()["puerto_sugerido"] == 22001
    )
    db.filas["DISTINCT ON (o.equipo_id)"] = [
        {"equipo_id": EQUIPO, "nombre": "EQUIPO-DE-PRUEBA", "puerto": 22009}
    ]
    db.filas["LEFT JOIN LATERAL"] = [fila(estado="pendiente", resultado_en=None)]
    datos = c.get(f"/api/flota/tunel/estado?equipo_id={EQUIPO}").json()
    assert (
        datos["puerto_asignado"] == datos["puerto_sugerido"] == 22009
        and datos["tunel"]["situacion"] == "solicitado"
    )
    assert datos["ajustes"]["automatico"] is False


# ── Retirada de la clave de la carga guardada ────────────────────────────────────────────────────


def carga_con_clave():
    carga = cargas.construir(
        orden_id="o1",
        equipo_id=EQUIPO,
        machine_guid="g",
        tipo="abrir_tunel_soporte",
        parametros=PLANOS,
        emitida_en="a",
        caduca_en="b",
        emitida_por="ana",
        clave="-----BEGIN OPENSSH PRIVATE KEY-----\nSECRETO\n-----END OPENSSH PRIVATE KEY-----\n",
    )
    import base64

    return base64.b64encode(json.dumps(carga).encode()).decode()


def test_la_purga_reescribe_la_carga_sin_la_clave_y_lo_anota():
    db = BaseFalsa()
    db.filas["FOR UPDATE SKIP LOCKED"] = [
        {
            "orden_id": "o1",
            "equipo_id": EQUIPO,
            "carga": carga_con_clave(),
            "estado": "ok",
        }
    ]
    assert asyncio.run(tunel_purga.purgar(db)) == 1
    (args,) = db.con("UPDATE flota_ordenes SET carga")
    nueva = leer_carga(args[1])
    assert (
        "clave" not in nueva
        and "SECRETO" not in args[1]
        and nueva["puerto_remoto"] == 22002
    )
    marca = json.loads(args[2])
    assert marca["clave_en_orden"] is False and marca["clave_eliminada_en"].endswith(
        "Z"
    )
    (anotado,) = db.con("INSERT INTO flota_registro")
    assert anotado[:2] == (
        EQUIPO,
        "o1",
    ) and "SECRETO" not in db.todo_como_texto().replace(carga_con_clave(), "")


def test_la_purga_solo_mira_ordenes_que_ya_no_se_entregan():
    sql = tunel_purga.SQL_CANDIDATAS
    assert "estado NOT IN ('pendiente', 'entregada') OR caduca_en <= NOW()" in sql
    assert "tipo = 'abrir_tunel_soporte'" in sql and '{"clave_en_orden": true}' in sql
    assert (
        "OR NOT parametros ? 'clave_en_orden'" in sql
    )  # también las insertadas a mano, sin marca
    db = BaseFalsa()
    assert asyncio.run(tunel_purga.purgar(db)) == 0 and not db.con(
        "UPDATE flota_ordenes"
    )


def test_una_orden_sin_clave_solo_queda_marcada_como_revisada():
    db = BaseFalsa()
    sin = cargas.sin_clave(carga_con_clave())
    db.filas["FOR UPDATE SKIP LOCKED"] = [
        {"orden_id": "o1", "equipo_id": EQUIPO, "carga": sin, "estado": "ok"}
    ]
    assert asyncio.run(tunel_purga.purgar(db)) == 0
    (args,) = db.con("UPDATE flota_ordenes SET carga")
    assert args[1] is None and json.loads(args[2]) == {"clave_en_orden": False}
    assert db.con("INSERT INTO flota_registro") == []


def test_la_purga_nunca_tumba_al_panel():
    class Rota:
        def acquire(self):
            raise RuntimeError("sin base de datos")

    assert asyncio.run(tunel_purga.purgar_sin_fallar(Rota())) == 0


def test_consultar_o_anular_una_orden_de_tunel_dispara_la_purga(entorno):
    c, db = entorno
    c.get("/api/flota/tunel/auditoria")
    assert len(db.con("FOR UPDATE SKIP LOCKED")) == 1
    db.fila["UPDATE flota_ordenes SET estado='anulada'"] = {
        "equipo_id": EQUIPO,
        "tipo": "abrir_tunel_soporte",
    }
    assert c.delete(f"/api/flota/ordenes/{EQUIPO}").status_code == 200
    assert len(db.con("FOR UPDATE SKIP LOCKED")) == 2


def test_el_panel_en_marcha_purga_solo(monkeypatch):
    monkeypatch.setattr(tunel_purga, "CADA_S", 0.01)
    llamadas = []

    async def ciclo(base, cada_s=60):
        llamadas.append(base)
        await asyncio.sleep(3600)

    monkeypatch.setattr(tunel_purga, "ciclo", ciclo)
    app = FastAPI()
    app.include_router(r_tunel)
    app.state.db = BaseFalsa()
    with TestClient(app):
        pass
    assert llamadas == [app.state.db]
