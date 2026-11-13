"""Aviso de ingreso desde un equipo nuevo: identificación del equipo, IP real y cuándo se avisa."""

import asyncio

from app.auth import aviso_sesion_nueva as av
from app.auth import sesion_dispositivo as sd


class Peticion:
    def __init__(self, cabeceras=None, cookies=None, ip="127.0.0.1"):
        self.headers = cabeceras or {}
        self.cookies = cookies or {}
        self.client = type("C", (), {"host": ip})()


class Respuesta:
    def __init__(self):
        self.cookies = {}

    def set_cookie(self, nombre, valor, **_):
        self.cookies[nombre] = valor


UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/142.0 Safari/537.36"


def test_dos_equipos_con_el_mismo_navegador_no_comparten_identificador():
    a, _, _ = sd.equipo_para_navegador("", UA)
    b, _, _ = sd.equipo_para_navegador("", UA)
    assert a != b and a.startswith("nav-") and len(a) > 20


def test_el_identificador_antiguo_se_renueva_y_el_nuevo_se_conserva():
    viejo = "nav-0123456789abcdef"
    assert sd.es_identificador_antiguo(viejo)
    nuevo, _, _ = sd.equipo_para_navegador(viejo, UA)
    assert nuevo != viejo and not sd.es_identificador_antiguo(nuevo)
    otra_vez, _, _ = sd.equipo_para_navegador(nuevo, UA)
    assert otra_vez == nuevo


def test_al_entrar_se_guarda_la_marca_del_equipo(monkeypatch):
    resp = Respuesta()
    d = sd.preparar_dispositivo(Peticion({"user-agent": UA}), resp, "normal")
    assert d["equipo_id"].startswith("nav-") and d["clase"] == "navegador"
    # con la marca antigua también se entrega una nueva
    resp2 = Respuesta()
    d2 = sd.preparar_dispositivo(
        Peticion({"user-agent": UA}, {sd.COOKIE_EQUIPO: "nav-0123456789abcdef"}),
        resp2,
        "normal",
    )
    assert d2["equipo_id"] != "nav-0123456789abcdef"


def test_la_ip_es_la_de_quien_entra_no_la_del_servidor():
    assert sd.ip_de(Peticion({"x-real-ip": "203.0.113.7"})) == "203.0.113.7"
    assert (
        sd.ip_de(Peticion({"x-forwarded-for": "198.51.100.9, 10.0.0.1"}))
        == "198.51.100.9"
    )
    assert sd.ip_de(Peticion()) == "127.0.0.1"
    assert sd.ip_de(None) == ""


class Base:
    def __init__(self, equipos=()):
        self.equipos = set(equipos)
        self.pref = {}

    async def execute(self, sql, *a):
        if "INSERT INTO auth_equipos_conocidos" in sql:
            self.equipos.add((a[0].lower(), a[1]))

    async def fetchval(self, sql, *a):
        if "FROM auth_equipos_conocidos" in sql and "equipo_id = $2" in sql:
            return 1 if (a[0].lower(), a[1]) in self.equipos else None
        if "FROM auth_equipos_conocidos" in sql:
            return 1 if any(u == a[0].lower() for u, _ in self.equipos) else None
        if "auth_aviso_sesion_pref" in sql:
            return self.pref.get(a[0].lower())
        if "FROM mailbox" in sql:
            return "Ana Pérez"
        return None

    async def fetch(self, sql, *a):
        return []


def _avisar(db, monkeypatch, **kw):
    enviados = []

    async def correo(cuenta, **datos):
        enviados.append((cuenta, datos))

    monkeypatch.setattr(av, "_enviar_correo", correo)
    monkeypatch.setattr(av, "_tablas_ok", True)
    r = asyncio.run(av.avisar_ingreso_nuevo(db, None, "ana@example.org", **kw))
    return r, enviados


def test_el_primer_equipo_de_una_cuenta_no_avisa(monkeypatch):
    db = Base()
    r, enviados = _avisar(
        db,
        monkeypatch,
        equipo_id="nav-AAA",
        nombre_equipo="Chrome en Windows",
        ip="203.0.113.7",
    )
    assert r["motivo"] == "primer_equipo" and not enviados
    assert ("ana@example.org", "nav-AAA") in db.equipos


def test_un_segundo_equipo_si_avisa_con_nombre_y_lugar(monkeypatch):
    db = Base({("ana@example.org", "nav-AAA")})
    r, enviados = _avisar(
        db,
        monkeypatch,
        equipo_id="nav-BBB",
        nombre_equipo="Firefox en Linux",
        ip="203.0.113.7",
    )
    assert r["avisado"] and r["motivo"] == "equipo_nuevo" and len(enviados) == 1
    datos = enviados[0][1]
    assert (
        datos["nombre_persona"] == "Ana Pérez"
        and datos["nombre_equipo"] == "Firefox en Linux"
    )
    assert "203.0.113.7" in datos["ubicacion"]
    assert ("ana@example.org", "nav-BBB") in db.equipos


def test_un_equipo_conocido_no_avisa(monkeypatch):
    db = Base({("ana@example.org", "nav-AAA")})
    r, enviados = _avisar(
        db, monkeypatch, equipo_id="nav-AAA", nombre_equipo="Chrome en Windows"
    )
    assert r["motivo"] == "equipo_conocido" and not enviados


def test_la_persona_puede_apagarlo_y_tecnologia_tambien(monkeypatch):
    db = Base({("ana@example.org", "nav-AAA")})
    db.pref["ana@example.org"] = False
    r, enviados = _avisar(db, monkeypatch, equipo_id="nav-CCC", nombre_equipo="x")
    assert r["motivo"] == "aviso_desactivado" and not enviados

    db2 = Base({("ana@example.org", "nav-AAA")})
    monkeypatch.setenv("AVISO_INGRESO_NUEVO", "0")
    r, enviados = _avisar(db2, monkeypatch, equipo_id="nav-DDD", nombre_equipo="x")
    assert r["motivo"] == "aviso_apagado_por_tecnologia" and not enviados
    assert (
        "ana@example.org",
        "nav-DDD",
    ) in db2.equipos, "se registra para no avisar después de golpe"


def test_la_red_interna_se_dice_como_tal(monkeypatch):
    assert asyncio.run(av._donde(None, "10.1.2.3")) == "Red interna de la organización"
    assert asyncio.run(av._donde(None, "")) == "desconocida"
