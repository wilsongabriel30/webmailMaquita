"""Avisos de correo al instante para la app móvil (AM-01): qué viaja y a quién se avisa."""

import asyncio
import json

from app.mobile import avisos_correo as ac


class Redis:
    def __init__(self, sesiones=()):
        self.sesiones = set(sesiones)
        self.claves = set()

    async def exists(self, clave):
        return clave in self.sesiones

    async def set(self, clave, valor, nx=False, ex=None):
        if nx and clave in self.claves:
            return None
        self.claves.add(clave)
        return True


class Base:
    def __init__(self, filas):
        self.filas = filas
        self.consultas = []

    async def fetch(self, sql, *args):
        self.consultas.append(sql)
        return [f for f in self.filas if f["cuenta"] in args[0]]

    async def execute(self, sql, *args):
        self.consultas.append(sql)


def fila(n, cuenta="ana@example.org", sid="s1"):
    return {
        "id": n,
        "cuenta": cuenta,
        "device_id": f"tel-{n}",
        "push_topic": f"disp_correo_{n:032x}",
        "sid": sid,
    }


def test_el_aviso_no_lleva_nada_del_correo():
    cuerpo = json.loads(ac.cuerpo_aviso("ana@example.org"))
    assert cuerpo == {"tipo": "correo_nuevo", "cuenta": "ana@example.org", "v": 1}
    assert not {"de", "asunto", "remitente", "subject", "from", "texto"} & set(cuerpo)


def test_el_tema_es_secreto_y_publicable_por_el_servidor():
    a, b = ac.nuevo_tema(), ac.nuevo_tema()
    assert (
        a != b and a.startswith("disp_correo_") and len(a) == len("disp_correo_") + 32
    )


def test_bloque_push_usa_el_servidor_por_el_que_entro_la_app(monkeypatch):
    monkeypatch.setattr(ac, "_TOKEN", "x")
    b = ac.bloque_push("mail.example.org:443", "disp_correo_abc", True)
    assert b == {
        "protocolo": "ntfy",
        "servidor": "https://mail.example.org:2587",
        "tema": "disp_correo_abc",
        "contenido": "ninguno",
    }
    assert (
        ac.bloque_push("mail.example.org", "disp_correo_abc", False) is None
    ), "avisos apagados"
    assert ac.bloque_push("mail.example.org", None, True) is None
    monkeypatch.setattr(ac, "_TOKEN", "")
    assert (
        ac.bloque_push("mail.example.org", "disp_correo_abc", True) is None
    ), "sin ntfy configurado"


def test_solo_se_avisa_a_telefonos_con_la_sesion_viva(monkeypatch):
    monkeypatch.setattr(ac, "_TOKEN", "x")
    db = Base([fila(1, sid="viva"), fila(2, sid="cerrada")])
    redis = Redis({"sess:ana@example.org:viva"})
    elegidos = asyncio.run(ac.telefonos_a_avisar(db, redis, ["ana@example.org"]))
    assert [t["id"] for t in elegidos] == [1]


def test_varios_correos_seguidos_no_son_una_rafaga(monkeypatch):
    monkeypatch.setattr(ac, "_TOKEN", "x")
    db, redis = Base([fila(1, sid="viva")]), Redis({"sess:ana@example.org:viva"})
    assert len(asyncio.run(ac.telefonos_a_avisar(db, redis, ["ana@example.org"]))) == 1
    assert asyncio.run(ac.telefonos_a_avisar(db, redis, ["ana@example.org"])) == []


def test_la_consulta_excluye_bajas_avisos_apagados_y_telefonos_olvidados(monkeypatch):
    monkeypatch.setattr(ac, "_TOKEN", "x")
    db = Base([])
    asyncio.run(ac.telefonos_a_avisar(db, Redis(), ["ana@example.org"]))
    sql = db.consultas[0]
    for condicion in (
        "is_active",
        "AND avisos",
        "push_topic IS NOT NULL",
        "sid IS NOT NULL",
        "last_sync > now()",
    ):
        assert condicion in sql


def test_sin_ntfy_configurado_no_se_hace_nada(monkeypatch):
    monkeypatch.setattr(ac, "_TOKEN", "")
    db = Base([fila(1)])
    assert (
        asyncio.run(
            ac.telefonos_a_avisar(
                db, Redis({"sess:ana@example.org:s1"}), ["ana@example.org"]
            )
        )
        == []
    )
    assert db.consultas == []
    ac.programar(db, Redis(), ["ana@example.org"])  # no lanza ni crea tareas


def test_avisar_publica_y_anota(monkeypatch):
    monkeypatch.setattr(ac, "_TOKEN", "x")
    monkeypatch.setattr(ac, "RETRASO_ENTREGA_S", 0)
    publicados = []

    async def falso(tema, cuenta):
        publicados.append((tema, cuenta))
        return True

    monkeypatch.setattr(ac, "_publicar", falso)
    db = Base([fila(1, sid="viva"), fila(2, cuenta="luis@example.org", sid="viva")])
    redis = Redis({"sess:ana@example.org:viva", "sess:luis@example.org:viva"})
    n = asyncio.run(
        ac.avisar(
            db, redis, ["ana@example.org", "LUIS@example.org", "nadie@example.org"]
        )
    )
    assert n == 2 and {c for _, c in publicados} == {
        "ana@example.org",
        "luis@example.org",
    }
    assert "avisos_enviados = avisos_enviados + 1" in db.consultas[-1]
