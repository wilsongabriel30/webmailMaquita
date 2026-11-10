"""Las etiquetas siguen al correo: reubicación con COPYUID, por Message-ID y borrado al eliminar."""

import pytest

from app.mail.services import etiquetas_reubicar as reub
from tests._bd_etiquetas_falsa import BDEtiquetasFalsa, fila

OWNER = "persona@example.com"


class Resp:
    def __init__(self, result="OK", lines=()):
        self.result = result
        self.lines = list(lines)


class ImapFalso:
    """Registra las órdenes; responde lo que se le programe."""

    def __init__(self, fetch_lines=(), search_lines=(), select_ok=True):
        self.ordenes = []
        self.fetch_lines = list(fetch_lines)
        self.search_lines = list(search_lines)
        self.select_ok = select_ok

    async def select(self, carpeta):
        self.ordenes.append(("select", carpeta))
        return Resp("OK" if self.select_ok else "NO")

    async def uid(self, cmd, *args):
        self.ordenes.append(("uid", cmd, *args))
        return Resp("OK", self.fetch_lines)

    async def uid_search(self, *args):
        self.ordenes.append(("uid_search", *args))
        return Resp("OK", self.search_lines)


@pytest.mark.asyncio
async def test_mover_con_copyuid_traslada_las_asignaciones():
    db = BDEtiquetasFalsa([fila(1, OWNER, "INBOX", 254, 22), fila(2, OWNER, "INBOX", 254, 23), fila(3, OWNER, "INBOX", 100, 22)])
    ctx = {"owner": OWNER, "folder": "INBOX", "uids": [254, 300], "action": "move", "message_ids": {}}
    n = await reub.completar_reubicacion(db, ImapFalso(), ctx, {254: 1095, 300: 1096}, "Archivo")
    assert n == 2
    claves = sorted((f["folder"], f["message_uid"], f["label_id"]) for f in db.filas)
    assert claves == [("Archivo", 1095, 22), ("Archivo", 1095, 23), ("INBOX", 100, 22)]
    assert all(f["faltante_desde"] is None for f in db.filas)


@pytest.mark.asyncio
async def test_mover_sin_copyuid_resuelve_por_message_id():
    db = BDEtiquetasFalsa([fila(1, OWNER, "INBOX", 7, 5)])
    imap = ImapFalso(search_lines=[b"41", b"SEARCH completed"])
    ctx = {"owner": OWNER, "folder": "INBOX", "uids": [7], "action": "move", "message_ids": {7: "<abc@x>"}}
    n = await reub.completar_reubicacion(db, imap, ctx, None, "Trabajo")
    assert n == 1
    assert [(f["folder"], f["message_uid"]) for f in db.filas] == [("Trabajo", 41)]
    assert imap.ordenes[0][0] == "select" and imap.ordenes[0][1].strip('"') == "Trabajo"
    assert any(o[0] == "uid_search" and "Message-ID" in o for o in imap.ordenes)


@pytest.mark.asyncio
async def test_mover_sin_forma_de_seguir_el_uid_no_borra_nada():
    db = BDEtiquetasFalsa([fila(1, OWNER, "INBOX", 7, 5)])
    imap = ImapFalso(search_lines=[b"SEARCH completed"])  # no se encuentra en destino
    ctx = {"owner": OWNER, "folder": "INBOX", "uids": [7], "action": "move", "message_ids": {7: "<abc@x>"}}
    n = await reub.completar_reubicacion(db, imap, ctx, None, "Trabajo")
    assert n == 0
    assert [(f["folder"], f["message_uid"]) for f in db.filas] == [("INBOX", 7)]


@pytest.mark.asyncio
async def test_archivar_sin_destino_usa_archive():
    db = BDEtiquetasFalsa([fila(1, OWNER, "INBOX", 9, 5)])
    ctx = {"owner": OWNER, "folder": "INBOX", "uids": [9], "action": "archive", "message_ids": {}}
    await reub.completar_reubicacion(db, ImapFalso(), ctx, {9: 3}, "")
    assert db.filas[0]["folder"] == "Archive" and db.filas[0]["message_uid"] == 3


@pytest.mark.asyncio
async def test_eliminar_borra_solo_esas_asignaciones():
    db = BDEtiquetasFalsa([fila(1, OWNER, "Trash", 1, 5), fila(2, OWNER, "Trash", 2, 5), fila(3, OWNER, "INBOX", 1, 5), fila(4, "otra@x", "Trash", 1, 9)])
    ctx = {"owner": OWNER, "folder": "Trash", "uids": [1], "action": "delete"}
    n = await reub.completar_reubicacion(db, None, ctx, None, "")
    assert n == 1
    assert sorted(f["id"] for f in db.filas) == [2, 3, 4]


@pytest.mark.asyncio
async def test_vaciar_carpeta_borra_todas_las_de_la_carpeta():
    db = BDEtiquetasFalsa([fila(1, OWNER, "Trash", 1, 5), fila(2, OWNER, "Trash", 2, 5), fila(3, OWNER, "INBOX", 1, 5)])
    ctx = {"owner": OWNER, "folder": "Trash", "uids": [], "action": "delete"}
    assert await reub.completar_reubicacion(db, None, ctx, None, "") == 2
    assert [f["id"] for f in db.filas] == [3]


@pytest.mark.asyncio
async def test_marcar_leido_no_toca_nada():
    db = BDEtiquetasFalsa([fila(1, OWNER, "INBOX", 1, 5)])
    ctx = {"owner": OWNER, "folder": "INBOX", "uids": [1], "action": "mark_read", "message_ids": {}}
    assert await reub.completar_reubicacion(db, ImapFalso(), ctx, None, "") == 0
    assert len(db.filas) == 1 and db.sql == []


@pytest.mark.asyncio
async def test_preparar_lee_message_id_solo_de_los_etiquetados():
    db = BDEtiquetasFalsa([fila(1, OWNER, "INBOX", 7, 5)])
    imap = ImapFalso(fetch_lines=[b"1 FETCH (UID 7 BODY[HEADER.FIELDS (MESSAGE-ID)] {30}", b"Message-ID: <id-7@ejemplo>", b""])
    ctx = await reub.preparar_reubicacion(db, imap, OWNER, "INBOX", [7, 8, 9], "move")
    assert ctx["message_ids"] == {7: "<id-7@ejemplo>"}
    fetch = [o for o in imap.ordenes if o[0] == "uid" and o[1] == "fetch"][0]
    assert fetch[2] == "7"  # no pide el 8 ni el 9
    assert "PEEK" in fetch[3]


@pytest.mark.asyncio
async def test_preparar_no_toca_imap_si_la_accion_no_mueve():
    db = BDEtiquetasFalsa([fila(1, OWNER, "INBOX", 7, 5)])
    imap = ImapFalso()
    ctx = await reub.preparar_reubicacion(db, imap, OWNER, "INBOX", [7], "delete")
    assert ctx["message_ids"] == {} and imap.ordenes == []
