"""Emisión de las órdenes del túnel de soporte: forma exacta de la carga firmada, dónde queda (y dónde no)
la clave privada, control de acceso, reparto de puertos y modo automático con un servidor de túneles simulado.
"""

import json

import pytest
from dobles_flota import (
    ADMIN,
    EQUIPO,
    GUID,
    OTRO,
    BaseFalsa,
    clave_de_firma,
    leer_carga,
)
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import require_operador
from app.flota import cargas, tunel, tunel_claves, tunel_puertos
from app.flota.router_equipos import router as r_equipos
from app.flota.router_ordenes import router as r_ordenes

HOST = "tuneles.example.org"
DESTINO = {"equipo_id": EQUIPO, "machine_guid": GUID, "nombre": "EQUIPO-DE-PRUEBA"}
MOTIVO = "Soporte a una portátil fuera de la oficina"


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    monkeypatch.setenv("FLOTA_TUNEL_HOST", HOST)
    for nombre in (
        "FLOTA_TUNEL_HOST_INTERNO",
        "FLOTA_TUNEL_BROKER",
        "FLOTA_TUNEL_PUERTO_SSH",
        "FLOTA_TUNEL_USUARIO",
    ):
        monkeypatch.delenv(nombre, raising=False)
    firma = clave_de_firma(tmp_path, monkeypatch)
    app = FastAPI()
    app.include_router(r_ordenes)
    app.include_router(r_equipos)
    db = BaseFalsa()
    db.filas["FROM flota_equipos WHERE estado='activo'"] = [DESTINO]
    app.state.db = db
    app.dependency_overrides[require_operador] = lambda: ADMIN
    yield TestClient(app), db, firma
    firma._privada.cache_clear()


def pedir(c, tipo="abrir_tunel_soporte", **cambios):
    cuerpo = {
        "tipo": tipo,
        "motivo": MOTIVO,
        "confirmacion": "CONFIRMO",
        "equipos": [EQUIPO],
        "parametros": {},
    }
    cuerpo.update(cambios)
    return c.post("/api/flota/ordenes", json=cuerpo)


def guardada(db):
    """(parametros de la columna, carga firmada descifrada, carga_b64, firma_b64) de la orden insertada."""
    (args,) = db.con("INSERT INTO flota_ordenes")
    return json.loads(args[3]), leer_carga(args[5]), args[5], args[6]


def test_sin_sesion_no_se_emite_ni_se_consulta(tmp_path, monkeypatch):
    from app.flota.router_tunel import router as r_tunel

    app = FastAPI()
    for r in (r_ordenes, r_equipos, r_tunel):
        app.include_router(r)
    app.state.db = BaseFalsa()
    c = TestClient(app)
    assert (
        c.post("/api/flota/ordenes", json={"tipo": "abrir_tunel_soporte"}).status_code
        == 401
    )
    assert c.get("/api/flota/tunel/auditoria").status_code == 401
    assert c.get(f"/api/flota/tunel/estado?equipo_id={EQUIPO}").status_code == 401
    assert app.state.db.ejecutado == []


def test_forma_exacta_de_la_carga_con_clave(entorno):
    c, db, firma = entorno
    privada, _, huella = tunel_claves.generar()
    r = pedir(c, parametros={"puerto_remoto": 22002, "minutos": 60, "clave": privada})
    assert r.status_code == 200, r.text
    columna, carga, carga_b64, firma_b64 = guardada(db)
    assert firma.verificar(carga_b64, firma_b64)
    orden_id = r.json()["emitidas"][0]["orden_id"]
    planos = {
        "host": HOST,
        "puerto_ssh": 443,
        "usuario": "tunel",
        "puerto_remoto": 22002,
        "minutos": 60,
    }
    assert carga == {
        "proposito": "maquita-flota-orden",
        "v": 1,
        "kid": firma.KID,
        "orden_id": orden_id,
        "equipo_id": EQUIPO,
        "machine_guid": GUID,
        "tipo": "abrir_tunel_soporte",
        **planos,
        "clave": privada,
        "parametros": planos,
        "emitida_en": carga["emitida_en"],
        "caduca_en": r.json()["caduca_en"],
        "emitida_por": "ana",
    }
    assert columna == {
        **planos,
        "modo": "manual",
        "clave_en_orden": True,
        "clave_huella": huella,
    }


def test_la_clave_solo_esta_en_la_carga_firmada(entorno):
    c, db, _ = entorno
    privada, _, _ = tunel_claves.generar()
    secreto = privada.splitlines()[1]
    r = pedir(c, parametros={"clave": privada})
    assert r.status_code == 200 and secreto not in r.text and "clave" not in r.json()
    carga_b64 = guardada(db)[2]
    resto = [(s, tuple(a for a in args if a != carga_b64)) for s, args in db.ejecutado]
    assert secreto not in json.dumps(resto, default=str)
    assert secreto.replace("/", "\\/") not in json.dumps(resto, default=str)
    for trozo in ("INSERT INTO flota_registro", "INSERT INTO admin_audit"):
        assert db.con(trozo) and "BEGIN OPENSSH" not in json.dumps(
            db.con(trozo), default=str
        )


def test_sin_clave_el_equipo_usa_la_que_tiene_instalada(entorno):
    c, db, _ = entorno
    assert pedir(c).status_code == 200
    columna, carga, _, _ = guardada(db)
    assert (
        "clave" not in carga
        and columna["clave_en_orden"] is False
        and "clave_huella" not in columna
    )
    assert carga["minutos"] == 30 and carga["puerto_remoto"] == 22001  # el menor libre


def test_validez_corta_de_las_ordenes_de_tunel(entorno):
    c, db, _ = entorno
    assert pedir(c, horas_validez=72).status_code == 400
    assert pedir(c, horas_validez=3).status_code == 200
    carga = guardada(db)[1]
    assert carga["emitida_en"] < carga["caduca_en"]
    (args,) = db.con("INSERT INTO flota_ordenes")
    assert (args[10] - args[9]).total_seconds() == 3 * 3600


def test_cerrar_no_lleva_nada_del_tunel(entorno):
    c, db, firma = entorno
    r = pedir(
        c,
        tipo="cerrar_tunel_soporte",
        confirmacion="",
        parametros={"host": "x.example", "clave": "no"},
    )
    assert r.status_code == 200, r.text
    columna, carga, carga_b64, firma_b64 = guardada(db)
    assert (
        columna == {}
        and carga["parametros"] == {}
        and carga["tipo"] == "cerrar_tunel_soporte"
    )
    assert not {
        "host",
        "puerto_ssh",
        "usuario",
        "puerto_remoto",
        "minutos",
        "clave",
    } & set(carga)
    assert firma.verificar(carga_b64, firma_b64)


def test_exige_motivo_confirmacion_y_un_solo_equipo(entorno):
    c, db, _ = entorno
    assert pedir(c, motivo="").status_code == 400
    assert pedir(c, confirmacion="").status_code == 400
    assert pedir(c, equipos=None, todos=True).status_code == 400
    db.filas["FROM flota_equipos WHERE estado='activo'"] = [
        DESTINO,
        {**DESTINO, "equipo_id": OTRO},
    ]
    assert pedir(c, equipos=[EQUIPO, OTRO]).status_code == 400
    assert pedir(c, parametros={"clave": "esto no es una clave"}).status_code == 400
    assert db.con("INSERT INTO flota_ordenes") == []


def test_las_demas_ordenes_se_firman_igual_que_antes(entorno):
    c, db, firma = entorno
    assert pedir(c, tipo="ping", confirmacion="", horas_validez=72).status_code == 200
    columna, carga, carga_b64, firma_b64 = guardada(db)
    assert columna == {} and firma.verificar(carga_b64, firma_b64)
    assert sorted(carga) == sorted(
        [
            "proposito",
            "v",
            "kid",
            "orden_id",
            "equipo_id",
            "machine_guid",
            "tipo",
            "parametros",
            "emitida_en",
            "caduca_en",
            "emitida_por",
        ]
    )


def test_reparto_de_puertos(entorno):
    c, db, _ = entorno
    db.filas["DISTINCT ON (o.equipo_id)"] = [
        {"equipo_id": OTRO, "nombre": "OTRO-EQUIPO", "puerto": 22001},
        {"equipo_id": EQUIPO, "nombre": "EQUIPO-DE-PRUEBA", "puerto": 22007},
    ]
    assert pedir(c).status_code == 200  # conserva el suyo
    assert guardada(db)[1]["puerto_remoto"] == 22007
    r = pedir(c, parametros={"puerto_remoto": 22001})  # el de otro equipo
    assert r.status_code == 409 and "OTRO-EQUIPO" in r.json()["detail"]
    assert db.con("pg_advisory_xact_lock")


def test_menor_puerto_libre_y_rango_agotado():
    from fastapi import HTTPException

    assert tunel_puertos.menor_libre({22001, 22002, 22004}) == 22003
    with pytest.raises(HTTPException) as e:
        tunel_puertos.menor_libre(range(22001, 23000))
    assert e.value.status_code == 409


def test_el_catalogo_del_panel_trae_los_ajustes_del_tunel(entorno):
    c, _, _ = entorno
    datos = c.get("/api/flota/catalogo").json()
    assert (
        datos["tunel"]["host_fuera"] == HOST and datos["tunel"]["automatico"] is False
    )
    assert datos["tunel"]["duraciones"] == [15, 30, 60, 120]
    assert (datos["tunel"]["puerto_min"], datos["tunel"]["puerto_max"]) == (
        22001,
        22999,
    )


def test_sin_clave_carga_sin_cambios_y_con_clave_se_retira():
    planos = {
        "host": HOST,
        "puerto_ssh": 443,
        "usuario": "tunel",
        "puerto_remoto": 22001,
        "minutos": 30,
    }
    comun = dict(
        orden_id="o",
        equipo_id="e",
        machine_guid="g",
        tipo="abrir_tunel_soporte",
        parametros=planos,
        emitida_en="a",
        caduca_en="b",
        emitida_por="ana",
    )
    import base64

    def b64(carga):
        return base64.b64encode(json.dumps(carga).encode()).decode()

    con = cargas.construir(**comun, clave="-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n")
    assert cargas.sin_clave(b64(cargas.construir(**comun))) is None
    assert leer_carga(cargas.sin_clave(b64(con))) == cargas.construir(**comun)
    assert cargas.sin_clave("no es base64 ni json") is None


# ── Fase B: modo automático con un servidor de túneles simulado ──────────────────────────────────


class BrokerFalso:
    def __init__(self, instaladas=None, libre=22001, falla=None):
        self.instaladas, self.libre, self.falla, self.llamadas = (
            instaladas or {},
            libre,
            falla,
            [],
        )

    async def listar(self):
        self.llamadas.append(("listar",))
        return dict(self.instaladas)

    async def puerto_libre(self):
        self.llamadas.append(("puerto-libre",))
        return self.libre

    async def alta(self, etiqueta, puerto, publica):
        if self.falla:
            raise self.falla
        self.llamadas.append(("alta", etiqueta, puerto, publica))

    async def baja(self, etiqueta):
        self.llamadas.append(("baja", etiqueta))


@pytest.fixture
def automatico(entorno, monkeypatch):
    c, db, firma = entorno
    falso = BrokerFalso()
    monkeypatch.setenv("FLOTA_TUNEL_BROKER", "true")
    monkeypatch.setattr(tunel.Broker, "desde_entorno", classmethod(lambda cls: falso))
    return c, db, firma, falso


def test_apagado_por_defecto_no_se_toca_el_servidor_de_tuneles(entorno, monkeypatch):
    c, db, _ = entorno

    def prohibido(cls):
        raise AssertionError(
            "con el modo automático apagado no se debe usar el servidor de túneles"
        )

    monkeypatch.setattr(tunel.Broker, "desde_entorno", classmethod(prohibido))
    assert pedir(c).status_code == 200
    assert pedir(c, tipo="cerrar_tunel_soporte").status_code == 200
    assert c.post(
        f"/api/flota/equipos/{EQUIPO}/retirar", json={"motivo": "Equipo dado de baja"}
    ).status_code in (200, 404)


def test_automatico_genera_el_par_revoca_el_anterior_e_instala_la_publica(automatico):
    c, db, firma, falso = automatico
    r = pedir(c)
    assert r.status_code == 200, r.text
    columna, carga, carga_b64, firma_b64 = guardada(db)
    etiqueta = "EQUIPO-DE-PRUEBA-11111111"
    assert [x[0] for x in falso.llamadas] == ["listar", "puerto-libre", "baja", "alta"]
    _, etq, puerto, publica = falso.llamadas[-1]
    assert (etq, puerto) == (etiqueta, 22001) and falso.llamadas[2] == (
        "baja",
        etiqueta,
    )
    assert carga["puerto_remoto"] == 22001 and firma.verificar(carga_b64, firma_b64)
    assert (
        tunel_claves.comprobar(carga["clave"])[1]
        == tunel_claves.huella(publica)
        == columna["clave_huella"]
    )
    assert columna["modo"] == "automatico" and columna["clave_en_orden"] is True
    assert carga["clave"].splitlines()[1] not in r.text


def test_automatico_evita_puertos_de_otros_en_el_servidor_y_en_el_panel(automatico):
    c, db, _, falso = automatico
    falso.instaladas = {22001: "AJENO-00000000", 22003: "EQUIPO-DE-PRUEBA-11111111"}
    falso.libre = 22002
    db.filas["DISTINCT ON (o.equipo_id)"] = [
        {"equipo_id": OTRO, "nombre": "OTRO-EQUIPO", "puerto": 22002}
    ]
    assert pedir(c).status_code == 200
    assert (
        guardada(db)[1]["puerto_remoto"] == 22003
    )  # ni el 22001 (servidor) ni el 22002 (panel)
    assert pedir(c, parametros={"puerto_remoto": 22001}).status_code == 409


def test_automatico_si_el_servidor_de_tuneles_falla_no_se_emite(automatico):
    from app.flota.broker import ErrorBroker

    c, db, _, falso = automatico
    falso.falla = ErrorBroker("El servidor de túneles no respondió en 10 s.")
    r = pedir(c)
    assert r.status_code == 502 and "no respondió" in r.json()["detail"]
    assert db.con("INSERT INTO flota_ordenes") == []


def test_automatico_con_clave_pegada_respeta_la_manual(automatico):
    c, db, _, falso = automatico
    privada, _, huella = tunel_claves.generar()
    assert (
        pedir(c, parametros={"clave": privada, "puerto_remoto": 22050}).status_code
        == 200
    )
    columna, carga, _, _ = guardada(db)
    assert (
        falso.llamadas == []
        and carga["clave"] == privada
        and columna["modo"] == "manual"
    )


def test_automatico_al_cerrar_se_revoca_la_clave(automatico):
    c, db, _, falso = automatico
    assert pedir(c, tipo="cerrar_tunel_soporte").status_code == 200
    assert falso.llamadas == [("baja", "EQUIPO-DE-PRUEBA-11111111")]
    (args,) = [
        a for a in db.con("INSERT INTO flota_registro") if "tunel_clave_revocada" in a
    ]
    assert json.loads(args[4]) == {"clave_revocada": True}
