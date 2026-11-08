"""Pruebas de adjuntos_lista (listado con clip y nombres)."""

import asyncio

from app.mail.services.adjuntos_lista import (
    _texto_respuesta,
    adjuntos_de_estructura,
    adjuntos_por_uid,
)

MIXTO = (
    '(("TEXT" "PLAIN" ("CHARSET" "utf-8") NIL NIL "7BIT" 10 1 NIL NIL NIL NIL)'
    '("APPLICATION" "PDF" ("NAME" "a.pdf") NIL NIL "BASE64" 100 NIL ("ATTACHMENT" ("FILENAME" "a.pdf")) NIL NIL)'
    '("TEXT" "XML" ("NAME" "b.xml") NIL NIL "BASE64" 50 2 NIL ("ATTACHMENT" ("FILENAME" "b.xml")) NIL NIL) "MIXED")'
)


def test_sin_adjuntos():
    assert adjuntos_de_estructura(
        '("TEXT" "PLAIN" ("CHARSET" "utf-8") NIL NIL "7BIT" 10 1 NIL NIL NIL NIL)'
    ) == (False, [])


def test_adjuntos_con_nombre():
    assert adjuntos_de_estructura(MIXTO) == (True, ["a.pdf", "b.xml"])


def test_inline_no_cuenta():
    s = '(("TEXT" "HTML" NIL NIL NIL "7BIT" 10 1 NIL NIL NIL NIL)("IMAGE" "PNG" ("NAME" "logo.png") "<c1>" NIL "BASE64" 100 NIL ("INLINE" ("FILENAME" "logo.png")) NIL NIL) "RELATED")'
    assert adjuntos_de_estructura(s) == (False, [])


def test_inline_llamado_attachment_no_cuenta():
    s = '("IMAGE" "JPEG" ("NAME" "Attachment-1.jpeg") "<c1>" NIL "BASE64" 100 NIL ("INLINE" ("FILENAME" "Attachment-1.jpeg")) NIL NIL)'
    assert adjuntos_de_estructura(s) == (False, [])


def test_nombre_con_parentesis():
    s = '("APPLICATION" "PDF" ("NAME" "informe (final).pdf") NIL NIL "BASE64" 100 NIL ("ATTACHMENT" ("FILENAME" "informe (final).pdf")) NIL NIL)'
    assert adjuntos_de_estructura(s) == (True, ["informe (final).pdf"])


def test_disposicion_attachment_sin_parametros():
    s = '("APPLICATION" "PDF" ("NAME" "x.pdf") NIL NIL "BASE64" 100 NIL ("ATTACHMENT" NIL) NIL NIL)'
    assert adjuntos_de_estructura(s) == (True, [])


def test_rfc2231_y_mime():
    s = (
        '("APPLICATION" "PDF" NIL NIL NIL "BASE64" 100 NIL ("ATTACHMENT" ("FILENAME*" "utf-8\'\'Factura%20n%C2%BA1.pdf")) NIL NIL)'
        '("APPLICATION" "PDF" NIL NIL NIL "BASE64" 100 NIL ("ATTACHMENT" ("FILENAME" "=?utf-8?B?w7FhbmTDui5wZGY=?=")) NIL NIL)'
    )
    assert adjuntos_de_estructura(s) == (True, ["Factura nº1.pdf", "ñandú.pdf"])


def test_literal_con_tildes():
    lineas = [
        b'1 FETCH (UID 7 BODYSTRUCTURE ("APPLICATION" "PDF" NIL NIL NIL "BASE64" 100 NIL ("ATTACHMENT" ("FILENAME" {15}',
        "Datos ñandú.pdf".encode("utf-8"),
        b")) NIL NIL))",
        b"Success",
    ]
    texto = _texto_respuesta(lineas)
    assert '"Datos ñandú.pdf"' in texto
    assert adjuntos_de_estructura(texto) == (True, ["Datos ñandú.pdf"])


class _Resp:
    def __init__(self, lines):
        self.result = "OK"
        self.lines = lines


class _ImapFalso:
    def __init__(self, lines=None, tarda=0.0):
        self.lines = lines or []
        self.tarda = tarda
        self.pedidos = []

    async def uid(self, cmd, conjunto, items):
        self.pedidos.append(conjunto)
        await asyncio.sleep(self.tarda)
        return _Resp(self.lines)


def test_adjuntos_por_uid_varios():
    imap = _ImapFalso(
        [
            b"1 FETCH (UID 10 BODYSTRUCTURE " + MIXTO.encode() + b")",
            b'2 FETCH (UID 11 BODYSTRUCTURE ("TEXT" "PLAIN" NIL NIL NIL "7BIT" 1 1 NIL NIL NIL NIL))',
            b"Success",
        ]
    )
    r = asyncio.run(adjuntos_por_uid(imap, [10, 11, 12]))
    assert r[10] == (True, ["a.pdf", "b.xml"])
    assert r[11] == (False, [])
    assert 12 not in r


def test_tiempo_agotado_marca_conexion_sucia(monkeypatch):
    from app.mail.services import adjuntos_lista

    monkeypatch.setattr(adjuntos_lista, "TIEMPO_MAX_S", 0.05)
    imap = _ImapFalso(tarda=0.5)
    assert asyncio.run(adjuntos_por_uid(imap, [1])) == {}
    assert getattr(imap, "conexion_sucia", False) is True


class _RedisFalso:
    def __init__(self):
        self.datos = {}

    async def mget(self, claves):
        return [self.datos.get(k) for k in claves]

    def pipeline(self):
        redis = self

        class _P:
            def __init__(self):
                self.ops = []

            def set(self, k, v, ex=None):
                self.ops.append((k, v))

            async def execute(self):
                for k, v in self.ops:
                    redis.datos[k] = v

        return _P()


def test_cache_redis_evita_segundo_fetch():
    redis = _RedisFalso()
    imap = _ImapFalso(
        [b"1 FETCH (UID 10 BODYSTRUCTURE " + MIXTO.encode() + b")", b"Success"]
    )
    r1 = asyncio.run(
        adjuntos_por_uid(imap, [10], redis=redis, username="u@x", folder="INBOX")
    )
    r2 = asyncio.run(
        adjuntos_por_uid(imap, [10], redis=redis, username="u@x", folder="INBOX")
    )
    assert r1 == r2 == {10: (True, ["a.pdf", "b.xml"])}
    assert len(imap.pedidos) == 1
