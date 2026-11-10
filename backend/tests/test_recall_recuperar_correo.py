"""Recuperar correo enviado: caché del destinatario, auditoría, lectura previa y paso a Borradores.

Sin red, sin BD, sin doveadm: todo lo externo se sustituye con dobles (incidente 09/11/2026).
"""

import json
from types import SimpleNamespace

import pytest

from app.mail.routers import recall
from app.mail.services import recuperar_correo as rc


# ----------------------------------------------------------------------------- dobles
class _Redis:
    """Redis mínimo: recuerda los DEL y las publicaciones."""

    def __init__(self):
        self.borradas: list[str] = []
        self.publicadas: list[tuple[str, dict]] = []

    async def smembers(self, _clave):
        return set()

    async def delete(self, *claves):
        self.borradas.extend(claves)

    async def publish(self, canal, datos):
        self.publicadas.append((canal, json.loads(datos)))


class _Db:
    def __init__(self, fallar=False):
        self.fallar = fallar
        self.inserciones: list[tuple] = []

    async def fetch(self, _sql):
        return [{"domain": "example.org"}, {"domain": "ALL"}]

    async def execute(self, sql, *args):
        if self.fallar:
            raise RuntimeError("column \"username\" does not exist")
        self.inserciones.append((sql, args))


class _Resp:
    def __init__(self, result="OK", lines=()):
        self.result = result
        self.lines = list(lines)


class _Imap:
    """Conexión IMAP falsa: Enviados con un mensaje cuyo UID es 77."""

    capabilities = ("MOVE", "UIDPLUS")

    def __init__(self, en_enviados=True):
        self.en_enviados = en_enviados
        self.seleccionada = None
        self.ordenes: list[tuple] = []

    async def select(self, carpeta):
        self.seleccionada = carpeta
        return _Resp()

    async def uid_search(self, *criterios):
        self.ordenes.append(("search",) + criterios)
        return _Resp(lines=[b"77", b"SEARCH completed."] if self.en_enviados else [b"", b"SEARCH completed."])

    async def uid(self, orden, *args):
        self.ordenes.append((orden,) + args)
        return _Resp(lines=[b"OK [COPYUID 1 77 5] Moved UIDs."])


def _peticion(redis, db):
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(redis=redis, db_pool=db)),
        client=SimpleNamespace(host="10.0.0.5"),
    )


@pytest.fixture
def entorno(monkeypatch):
    """Simula doveadm y la sesión IMAP del remitente; devuelve los dobles para inspeccionar."""
    redis, db, imap = _Redis(), _Db(), _Imap()
    monkeypatch.setattr(
        recall.subprocess, "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout="guid 12\n"),
    )
    monkeypatch.setattr(recall, "_doveadm_search", lambda dest, mid: [("guid", "12")])
    monkeypatch.setattr(
        recall, "_doveadm_fetch_info",
        lambda dest, mid: {"folders": ["Archive"], "flags": "\\Seen", "was_read": True, "subject": "Hola"},
    )
    expunges: list[tuple] = []
    monkeypatch.setattr(
        recall, "_doveadm_expunge",
        lambda dest, mid, carpetas=None: expunges.append((dest, carpetas)) or True,
    )

    async def _clave(_req, _u):
        return "clave"

    class _Pool:
        async def __aenter__(self):
            return imap

        async def __aexit__(self, *exc):
            return False

    monkeypatch.setattr(recall, "get_user_password", _clave)
    monkeypatch.setattr(recall, "get_imap_login_user", _clave)
    monkeypatch.setattr(recall, "get_pooled_imap", lambda u, p: _Pool())
    return SimpleNamespace(redis=redis, db=db, imap=imap, expunges=expunges)


async def _recuperar(entorno, destinatarios, db=None):
    body = recall.RecallRequest(message_id="<abc@example.org>", recipients=destinatarios)
    return await recall.recall_message(
        _peticion(entorno.redis, db or entorno.db), body, username="test@example.org"
    )


# ----------------------------------------------------------------------------- pruebas
async def test_expunge_en_carpeta_real_e_invalida_cache_del_destinatario(entorno):
    salida = await _recuperar(entorno, ["tecnologia@example.org"])

    # Se expurga donde doveadm vio el mensaje.
    assert entorno.expunges == [("tecnologia@example.org", ["Archive"])]
    # Caché del destinatario: INBOX y la carpeta real, con sus índices y listados.
    assert "folders:tecnologia@example.org" in entorno.redis.borradas
    assert "uids:tecnologia@example.org:INBOX:" in entorno.redis.borradas
    assert "uids:tecnologia@example.org:Archive:" in entorno.redis.borradas
    assert salida["results"][0]["folders"] == ["INBOX", "Archive"]
    # Aviso por WebSocket al destinatario (mismo canal que el correo nuevo).
    canal, datos = entorno.redis.publicadas[0]
    assert canal == "ws:user:tecnologia@example.org"
    assert datos == {"type": rc.TIPO_EVENTO_WS, "folders": ["INBOX", "Archive"]}


async def test_recuperado_aunque_ya_lo_haya_leido(entorno):
    salida = await _recuperar(entorno, ["tecnologia@example.org"])
    r = salida["results"][0]
    assert r["status"] == "recalled"
    assert r["was_read"] is True
    assert r["detail"] == "Recuperado (ya lo había leído)"
    assert salida["summary"]["recalled"] == 1


async def test_auditoria_con_columnas_reales(entorno):
    await _recuperar(entorno, ["tecnologia@example.org"])
    sql, args = entorno.db.inserciones[0]
    assert "INSERT INTO audit_log (admin_user, action, target, details, ip_address)" in sql
    assert "username" not in sql
    assert args[0] == "test@example.org"
    assert args[1] == rc.ACCION_AUDITORIA
    assert args[2] == "<abc@example.org>"
    detalles = json.loads(args[3])
    assert detalles["remitente"] == "test@example.org"
    assert detalles["message_id"] == "<abc@example.org>"
    assert detalles["destinatarios"] == [
        {
            "destinatario": "tecnologia@example.org",
            "resultado": "recalled",
            "leido": True,
            "carpetas": ["INBOX", "Archive"],
        }
    ]
    assert detalles["movido_a_borradores"] is True
    assert args[4] == "10.0.0.5"


async def test_error_de_auditoria_queda_en_el_log(entorno, caplog):
    db = _Db(fallar=True)
    with caplog.at_level("ERROR"):
        salida = await _recuperar(entorno, ["tecnologia@example.org"], db=db)
    assert salida["results"][0]["status"] == "recalled"  # la recuperación no se cae
    assert any("audit_log" in m for m in caplog.messages)


async def test_todo_local_recuperado_pasa_el_enviado_a_borradores(entorno):
    salida = await _recuperar(entorno, ["tecnologia@example.org"])
    assert salida["movido_a_borradores"] is True
    assert "Borradores" in salida["message"]
    ordenes = entorno.imap.ordenes
    assert ("search", "HEADER", "Message-ID", '"<abc@example.org>"') in ordenes
    assert ("store", "77", "+FLAGS", "(\\Draft $Recuperado)") in ordenes
    assert ("move", "77", "Drafts") in ordenes
    # Caché del remitente: Enviados y Borradores.
    assert "uids:test@example.org:Sent:" in entorno.redis.borradas
    assert "uids:test@example.org:Drafts:" in entorno.redis.borradas


async def test_con_destinatario_externo_no_se_mueve(entorno, monkeypatch):
    async def _sin_envio(*a, **k):
        return True

    monkeypatch.setattr(recall, "_send_external_recall_request", _sin_envio)
    salida = await _recuperar(entorno, ["tecnologia@example.org", "alguien@gmail.com"])
    assert salida["movido_a_borradores"] is False
    assert entorno.imap.ordenes == []
    estados = {r["recipient"]: r["status"] for r in salida["results"]}
    assert estados["alguien@gmail.com"] == "external_request_sent"
    assert salida["summary"]["external"] == 1


def test_decision_de_mover():
    ok = {"status": "recalled"}
    assert rc.decidir_mover_a_borradores([ok]) is True
    assert rc.decidir_mover_a_borradores([ok, {"status": "not_found"}]) is True
    assert rc.decidir_mover_a_borradores([{"status": "not_found"}]) is False
    assert rc.decidir_mover_a_borradores([ok, {"status": "error"}]) is False
    assert rc.decidir_mover_a_borradores([ok, {"status": "external"}]) is False
    assert rc.decidir_mover_a_borradores([ok, {"status": "external_request_sent"}]) is False
    assert rc.decidir_mover_a_borradores([]) is False


def test_carpetas_a_invalidar_siempre_inbox_sin_repetir():
    assert rc.carpetas_a_invalidar(None) == ["INBOX"]
    assert rc.carpetas_a_invalidar(["INBOX", "Junk", "Junk", ""]) == ["INBOX", "Junk"]


async def test_mover_a_borradores_si_no_esta_en_enviados():
    imap = _Imap(en_enviados=False)
    salida = await rc.mover_a_borradores(imap, "<x@example.org>")
    assert salida["movido"] is False
    assert all(o[0] != "move" for o in imap.ordenes)


def test_fetch_info_lee_carpetas_y_lectura(monkeypatch):
    monkeypatch.setattr(
        recall.subprocess, "run",
        lambda *a, **k: SimpleNamespace(
            returncode=0,
            stdout="mailbox: INBOX\nuid: 5\nhdr.subject: Hola\nflags: \\Seen \\Recent\n",
        ),
    )
    info = recall._doveadm_fetch_info("a@example.org", "<x>")
    assert info["folders"] == ["INBOX"]
    assert info["was_read"] is True


async def test_check_previo_no_presenta_la_lectura_como_impedimento(entorno):
    body = recall.RecallRequest(message_id="<abc@example.org>", recipients=["tecnologia@example.org"])
    salida = await recall.check_recallable(_peticion(entorno.redis, entorno.db), body, username="test@example.org")
    c = salida["checks"][0]
    assert c["can_recall"] is True
    assert c["reason"] == "Recuperable (ya lo leyó)"
