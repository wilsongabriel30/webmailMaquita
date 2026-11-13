"""Botón «Enviar mensaje» de las alertas: el texto, el registro, el freno de 24 horas y los permisos."""

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import organizacion
from app.alertas_seguridad import mensaje_a_persona as redaccion
from app.alertas_seguridad import mensajes
from app.alertas_seguridad.ataques import agrupar
from app.auth import dependencies

ADMIN = {"id": 7, "username": "ana", "role": "admin", "session_id": 1, "totp": True}
CUENTA = "persona@ejemplo.org"
T0 = datetime(2026, 11, 13, 21, 0, tzinfo=timezone.utc)
TECNICISMOS = re.compile(
    r"\b(imap|smtp|pop3?|activesync|ip|protocolo|puerto|autenticaci[oó]n|servidor smtp)\b",
    re.I,
)
DIRECCION_DE_RED = re.compile(r"\b\d{1,3}(\.\d{1,3}){3}\b")


def filas(pais="EC", cuenta=CUENTA, n=3):
    return [
        {
            "cuenta": cuenta,
            "ip": f"198.51.100.{i}",
            "pais": pais,
            "servicio": "imap",
            "ok": 0,
            "fallos": 40,
            "hora": T0 - timedelta(hours=i),
        }
        for i in range(n)
    ]


def ataque(pais="EC"):
    return agrupar(filas(pais))[0]


# ── La redacción ──────────────────────────────────────────────────────────────


def test_el_texto_dice_que_paso_que_hacer_y_que_pasara():
    m = redaccion.redactar(
        CUENTA,
        "Ana Pérez",
        T0,
        url_correo="https://correo.ejemplo.org",
        zona=ZoneInfo("America/Guayaquil"),
    )
    c = m["cuerpo"]
    assert c.startswith("Buen día, Ana Pérez:")
    assert f"intenta entrar a su cuenta {CUENTA}" in c
    assert "con una contraseña equivocada" in c
    assert "El último intento fue el 13/11/2026, entre las 16:00 y las 17:00." in c
    assert "Actualice la contraseña guardada" in c
    assert "quite la cuenta y vuelva a agregarla" in c
    assert "Si no reconoce ese celular o programa" in c
    assert "desactivará el acceso a su correo desde ese celular o programa" in c
    assert "Su correo por la web (https://correo.ejemplo.org) seguirá funcionando" in c
    assert c.rstrip().endswith("Tecnología")
    assert "celular" in m["asunto"]


def test_el_texto_no_trae_direcciones_de_red_ni_tecnicismos():
    for interna in (False, True):
        m = redaccion.redactar(CUENTA, "Ana", T0, desde_red_interna=interna)
        todo = m["asunto"] + "\n" + m["cuerpo"]
        assert not TECNICISMOS.search(todo), TECNICISMOS.search(todo)
        assert not DIRECCION_DE_RED.search(todo)
        assert "198.51.100" not in todo


def test_trata_de_usted():
    c = redaccion.redactar(CUENTA, "Ana", T0)["cuerpo"].lower()
    for tuteo in (
        " tu ",
        " tus ",
        " tienes",
        " puedes",
        " abre ",
        " revisa ",
        "avísanos",
    ):
        assert tuteo not in c
    assert "su cuenta" in c and "le pedimos" in c


def test_sin_nombre_ni_fecha_sigue_siendo_correcto():
    c = redaccion.redactar(CUENTA)["cuerpo"]
    assert c.startswith("Buen día:\n") and "El último intento" not in c
    assert "Su correo por la web seguirá funcionando" in c


def test_si_el_equipo_estaba_en_la_red_interna_lo_dice_sin_tecnicismos():
    c = redaccion.redactar(CUENTA, desde_red_interna=True)["cuerpo"]
    assert "conectado a la red de la institución" in c


def test_el_enlace_de_la_aplicacion_solo_aparece_si_esta_configurado():
    assert "aplicación" not in redaccion.redactar(CUENTA)["cuerpo"]
    c = redaccion.redactar(CUENTA, enlace_app="https://correo.ejemplo.org/app")[
        "cuerpo"
    ]
    assert "aplicación de correo de la institución" in c
    assert "https://correo.ejemplo.org/app" in c


def test_procede_solo_con_intentos_del_pais_o_de_la_red_interna():
    assert redaccion.procede(ataque("EC"), True, False, "EC")
    assert redaccion.procede(ataque("LAN"), True, False, "EC")
    assert not redaccion.procede(
        ataque("ES"), True, False, "EC"
    )  # es un ataque de fuera
    assert not redaccion.procede(
        ataque("EC"), False, False, "EC"
    )  # la cuenta no existe
    assert not redaccion.procede(ataque("EC"), True, True, "EC")  # ya está cerrada


def test_el_correo_sale_firmado_por_tecnologia_y_las_respuestas_van_a_tecnologia():
    m = redaccion.componer(
        "avisos@ejemplo.org",
        "tecnologia@ejemplo.org",
        CUENTA,
        "Asunto\r\nBcc: otra@ejemplo.org",
        "Hola\r\nmundo",
    )
    assert m["From"] == "Tecnología <avisos@ejemplo.org>"
    assert m["To"] == CUENTA and m["Reply-To"] == "tecnologia@ejemplo.org"
    assert m["Subject"] == "Asunto Bcc: otra@ejemplo.org" and m["Bcc"] is None
    assert m.get_content() == "Hola\nmundo\n"
    con_nombre = redaccion.componer(
        "Mesa de ayuda <a@ejemplo.org>", "", CUENTA, "x", "y"
    )
    assert con_nombre["From"] == "Mesa de ayuda <a@ejemplo.org>"
    assert con_nombre["Reply-To"] is None
    assert redaccion.direccion("Mesa de ayuda <a@ejemplo.org>") == "a@ejemplo.org"


# ── Las rutas, con base de datos y transporte simulados ───────────────────────


class BaseFalsa:
    def __init__(self, con_tabla=True, activa=True, protegida=False, accesos=None):
        self.con_tabla, self.activa, self.protegida = con_tabla, activa, protegida
        self.accesos = filas() if accesos is None else accesos
        self.mensajes: list[dict] = []
        self.auditoria: list[tuple] = []

    async def fetchval(self, sql, *args):
        if "to_regclass" in sql:
            tabla = args[0] if args else "auth_cuentas_solo_web"
            return tabla if (tabla != mensajes.TABLA or self.con_tabla) else None
        if "FROM mailbox" in sql:
            return 1 if self.activa and args[0] == CUENTA else None
        if "FROM auth_cuentas_solo_web" in sql:
            return 1 if self.protegida else None
        raise AssertionError(sql)

    async def fetch(self, sql, *args):
        if "FROM seg_accesos_detalle" in sql:
            return [f for f in self.accesos if f["cuenta"] == args[0]]
        if "DISTINCT ON (cuenta)" in sql:
            ahora = datetime.now(timezone.utc)
            por_cuenta = {}
            for m in self.mensajes:
                por_cuenta[m["cuenta"]] = {
                    **m,
                    "reciente": m["enviado"] > ahora - timedelta(hours=24),
                }
            return [v for k, v in por_cuenta.items() if k in args[0]]
        if "FROM mailbox" in sql:
            return [{"username": CUENTA, "name": "Ana Pérez"}]
        raise AssertionError(sql)

    async def fetchrow(self, sql, *args):
        if sql.startswith(f"SELECT enviado, enviado_por FROM {mensajes.TABLA}"):
            limite = datetime.now(timezone.utc) - timedelta(hours=24)
            previos = [
                m
                for m in self.mensajes
                if m["cuenta"] == args[0] and m["enviado"] > limite
            ]
            return previos[-1] if previos else None
        if sql.startswith(f"INSERT INTO {mensajes.TABLA}"):
            cuenta, asunto, cuerpo, remitente, por = args
            m = {
                "id": len(self.mensajes) + 1,
                "cuenta": cuenta,
                "asunto": asunto,
                "cuerpo": cuerpo,
                "remitente": remitente,
                "enviado_por": por,
                "enviado": datetime.now(timezone.utc),
            }
            self.mensajes.append(m)
            return m
        raise AssertionError(sql)

    async def execute(self, sql, *args):
        assert "INSERT INTO admin_audit" in sql
        self.auditoria.append(args)


@pytest.fixture
def entorno(monkeypatch):
    app = FastAPI()
    app.include_router(mensajes.router)
    db = BaseFalsa()
    app.state.db = db
    app.dependency_overrides[mensajes.solo_administradores] = lambda: ADMIN
    salidas = []

    async def transporte(mensaje, sobre, destinatario):
        salidas.append((mensaje, sobre, destinatario))

    monkeypatch.setattr(mensajes, "entregar", transporte)
    return TestClient(app), db, salidas, app


CUERPO = {
    "cuenta": CUENTA,
    "asunto": "Revise su celular",
    "cuerpo": "Buen día:\n\nTexto.",
}
RUTA = "/api/alertas-seguridad/mensajes"


def test_envia_a_la_cuenta_de_la_alerta_y_lo_registra(entorno):
    c, db, salidas, _ = entorno
    r = c.post(RUTA, json=CUERPO)
    assert r.status_code == 200 and r.json()["enviado_por"] == "ana"
    ((correo, sobre, destinatario),) = salidas
    assert destinatario == CUENTA and correo["To"] == CUENTA
    avisos = (
        f"postmaster@{organizacion.dominio_principal()}"  # el remitente de los avisos
    )
    assert sobre == avisos and correo["From"] == f"Tecnología <{avisos}>"
    assert correo["Reply-To"] == avisos
    assert correo["Subject"] == "Revise su celular"
    (m,) = db.mensajes
    assert (m["cuenta"], m["enviado_por"], m["cuerpo"]) == (
        CUENTA,
        "ana",
        "Buen día:\n\nTexto.",
    )
    (auditado,) = db.auditoria
    assert auditado[2] == "alerta_mensaje_a_persona" and auditado[3] == CUENTA


def test_remitente_y_respuestas_configurables(entorno, monkeypatch):
    c, _, salidas, _ = entorno
    monkeypatch.setenv(
        "ORG_REMITENTE_MENSAJES_ALERTAS", "Soporte <soporte@ejemplo.org>"
    )
    monkeypatch.setenv("ORG_CORREO_TECNOLOGIA", "tecnologia@ejemplo.org")
    assert c.post(RUTA, json=CUERPO).status_code == 200
    correo, sobre, _ = salidas[0]
    assert (
        sobre == "soporte@ejemplo.org"
        and correo["From"] == "Soporte <soporte@ejemplo.org>"
    )
    assert correo["Reply-To"] == "tecnologia@ejemplo.org"


def test_freno_de_24_horas_pide_confirmacion(entorno):
    c, db, salidas, _ = entorno
    assert c.post(RUTA, json=CUERPO).status_code == 200
    r = c.post(RUTA, json=CUERPO)
    assert r.status_code == 409 and "últimas 24 horas" in r.json()["detail"]
    assert len(salidas) == 1 and len(db.mensajes) == 1
    assert c.post(RUTA, json={**CUERPO, "confirmar": True}).status_code == 200
    assert len(salidas) == 2 and len(db.mensajes) == 2


def test_pasadas_24_horas_no_hace_falta_confirmar(entorno):
    c, db, salidas, _ = entorno
    assert c.post(RUTA, json=CUERPO).status_code == 200
    db.mensajes[0]["enviado"] -= timedelta(hours=25)
    assert c.post(RUTA, json=CUERPO).status_code == 200 and len(salidas) == 2


def test_no_envia_a_cuentas_sin_alerta_de_este_tipo(entorno):
    c, db, salidas, _ = entorno
    otra = c.post(RUTA, json={**CUERPO, "cuenta": "otra@ejemplo.org"})
    assert otra.status_code == 404
    db.accesos = filas("ES")  # ataque del exterior: no es el celular de la persona
    assert c.post(RUTA, json=CUERPO).status_code == 404
    db.accesos, db.protegida = filas(), True  # ya cerrada
    assert c.post(RUTA, json=CUERPO).status_code == 404
    db.protegida, db.accesos = False, filas(n=2)  # dos direcciones no son alerta
    assert c.post(RUTA, json=CUERPO).status_code == 404
    assert salidas == [] and db.mensajes == []


def test_sin_texto_no_envia(entorno):
    c, _, salidas, _ = entorno
    assert c.post(RUTA, json={**CUERPO, "cuerpo": "  \n "}).status_code == 400
    assert c.post(RUTA, json={**CUERPO, "asunto": ""}).status_code == 400
    assert salidas == []


def test_si_el_envio_falla_no_queda_registrado(entorno, monkeypatch):
    c, db, _, _ = entorno

    async def roto(*_):
        raise RuntimeError("sin transporte")

    monkeypatch.setattr(mensajes, "entregar", roto)
    r = c.post(RUTA, json=CUERPO)
    assert r.status_code == 502 and "no pudo enviar" in r.json()["detail"]
    assert db.mensajes == [] and db.auditoria == []


def test_sin_la_migracion_avisa_y_la_lista_no_ofrece_el_boton(entorno):
    c, db, _, _ = entorno
    db.con_tabla = False
    assert c.post(RUTA, json=CUERPO).status_code == 404


def test_solo_administradores(entorno, monkeypatch):
    c, db, salidas, app = entorno
    app.dependency_overrides.clear()
    assert c.post(RUTA, json=CUERPO).status_code == 401  # sin sesión

    async def lector(_):
        return {"id": 9, "username": "luis", "role": "viewer"}

    monkeypatch.setattr(dependencies, "get_current_admin", lector)
    assert c.post(RUTA, json=CUERPO).status_code == 403
    assert salidas == [] and db.mensajes == []

    async def administradora(_):
        return dict(ADMIN)

    monkeypatch.setattr(dependencies, "get_current_admin", administradora)
    assert c.post(RUTA, json=CUERPO).status_code == 200 and len(salidas) == 1


# ── Lo que ve la pantalla ─────────────────────────────────────────────────────


async def _anotar(db, ataques):
    await mensajes.anotar(db, ataques)
    return ataques


@pytest.mark.parametrize("pais, se_puede", [("EC", True), ("ES", False)])
def test_la_alerta_trae_el_borrador_solo_si_procede(pais, se_puede):
    import asyncio

    a = {**ataque(pais), "existe": True, "protegida": False}
    (a,) = asyncio.run(_anotar(BaseFalsa(), [a]))
    m = a["mensaje"]
    assert (
        m["se_puede_enviar"] is se_puede and m["enviado"] is None and not m["reciente"]
    )
    assert bool(m["cuerpo"]) is se_puede
    if se_puede:
        assert m["cuerpo"].startswith("Buen día, Ana Pérez:")
        assert not DIRECCION_DE_RED.search(m["cuerpo"])


def test_la_alerta_muestra_el_ultimo_envio():
    import asyncio

    db = BaseFalsa()
    db.mensajes.append(
        {"cuenta": CUENTA, "enviado_por": "ana", "enviado": datetime.now(timezone.utc)}
    )
    a = {**ataque(), "existe": True, "protegida": False}
    asyncio.run(_anotar(db, [a]))
    assert a["mensaje"]["enviado_por"] == "ana" and a["mensaje"]["reciente"] is True
    assert a["mensaje"]["enviado"]


def test_sin_la_migracion_la_alerta_queda_como_estaba():
    import asyncio

    a = {**ataque(), "existe": True, "protegida": False}
    asyncio.run(_anotar(BaseFalsa(con_tabla=False), [a]))
    assert "mensaje" not in a
