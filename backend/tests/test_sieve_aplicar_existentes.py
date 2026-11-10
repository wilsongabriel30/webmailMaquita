"""Aplicar reglas a los correos ya existentes: criterios IMAP, evaluación local y orquestación."""

import pytest

from app.sieve.aplicar_existentes import (
    Cabecera,
    Resultado,
    aplicar_regla_existentes,
    criterio_imap,
    cumple,
    parsear_cabecera,
    parsear_fetch,
    uids_que_cumplen,
)
from app.sieve.modelos import FilterAction, FilterCondition, FilterRule


def c(field, operator, value="", header=None):
    return FilterCondition(field=field, operator=operator, value=value, header=header)


def test_criterios_imap():
    assert criterio_imap(c("from", "contains", "direccion@example.org")) == (
        'FROM "direccion@example.org"',
        False,
    )
    assert criterio_imap(c("recipients", "contains", "x@example.org")) == (
        'OR TO "x@example.org" CC "x@example.org"',
        False,
    )
    assert criterio_imap(c("subject", "is", "Hola")) == ('SUBJECT "Hola"', False)
    assert criterio_imap(c("size", "over", "200")) == ("LARGER 204800", True)
    assert criterio_imap(c("size", "under", "2")) == ("SMALLER 2048", True)
    assert criterio_imap(c("body", "contains", "factura")) == ('BODY "factura"', True)
    assert criterio_imap(c("body", "not_contains", "factura")) == (
        'NOT BODY "factura"',
        True,
    )
    assert criterio_imap(c("header", "exists", "", header="X-Spam-Flag")) == (
        'HEADER X-Spam-Flag ""',
        True,
    )
    assert criterio_imap(c("list", "contains", "lista.example.org")) == (
        'HEADER List-Id "lista.example.org"',
        False,
    )
    # Patrón: acota por el trozo literal más largo
    assert criterio_imap(c("subject", "matches", "*Report Domain*")) == (
        'SUBJECT "Report Domain"',
        False,
    )
    # Sin acotación posible
    assert criterio_imap(c("from", "not_contains", "x")) == (None, False)
    assert criterio_imap(c("subject", "regex", "^RE:")) == (None, False)
    assert criterio_imap(c("subject", "contains", 'con "comillas"')) == (None, False)
    assert criterio_imap(c("subject", "contains", "año")) == (None, False)
    assert criterio_imap(c("subject", "matches", "*a*")) == (None, False)


def cabecera():
    return parsear_cabecera(
        7,
        3000,
        "From: Direccion <Direccion@Example.org>\r\nTo: yo@example.org, Otro <otro@example.org>\r\n"
        "Cc: cursos@example.org\r\nSubject: =?UTF-8?Q?Cotizaci=C3=B3n?= LAPTOP\r\nList-Id: <lista.example.org>\r\n"
        "X-Prioridad: alta\r\n\r\n",
    )


def test_parsear_cabecera():
    cab = cabecera()
    assert cab.uid == 7 and cab.size == 3000
    assert cab.direcciones["from"] == ["Direccion@Example.org"]
    assert cab.direcciones["to"] == ["yo@example.org", "otro@example.org"]
    assert cab.asunto == "Cotización LAPTOP"
    assert cab.encabezados["list-id"] == ["<lista.example.org>"]


def test_cumple_direcciones_y_asunto():
    cab = cabecera()
    assert cumple(
        c("from", "contains", "direccion@example.org"), cab
    )  # sin distinguir mayúsculas
    assert cumple(c("from", "is", "direccion@example.org"), cab)
    assert not cumple(c("from", "is", "direccion"), cab)
    assert cumple(
        c("from", "contains", "Direccion <"), cab
    )  # «contiene» mira el encabezado entero
    assert not cumple(
        c("from", "matches", "Direccion <*"), cab
    )  # el patrón, solo la dirección
    assert cumple(c("recipients", "contains", "cursos@"), cab)
    assert cumple(c("to", "not_contains", "cursos@"), cab)
    assert cumple(c("subject", "matches", "cotiz*laptop"), cab)
    assert cumple(c("subject", "regex", "^Cotizaci.n"), cab)
    assert not cumple(c("subject", "not_regex", "^Cotizaci.n"), cab)
    assert cumple(c("header", "is", "alta", header="X-Prioridad"), cab)
    assert cumple(c("header", "exists", "", header="X-Prioridad"), cab)
    assert cumple(c("header", "not_exists", "", header="X-Nada"), cab)
    assert cumple(c("list", "contains", "lista.example.org"), cab)
    assert cumple(c("size", "over", "2"), cab) and not cumple(
        c("size", "over", "3"), cab
    )
    assert not cumple(
        c(
            "subject",
            "regex",
            "(",
        ),
        cab,
    )  # regex inválida: no cumple, no revienta


def test_parsear_fetch():
    lines = [
        b"1 FETCH (UID 11 RFC822.SIZE 500 BODY[HEADER.FIELDS (FROM TO CC SUBJECT LIST-ID)] {40}",
        b"From: a@example.org\r\nSubject: Uno\r\n\r\n",
        b")",
        b"2 FETCH (UID 12 RFC822.SIZE 600 BODY[HEADER.FIELDS (FROM TO CC SUBJECT LIST-ID)] {40}",
        b"From: b@example.org\r\nSubject: Dos\r\n\r\n",
        b")",
        b"Fetch completed (0.001 + 0.000 secs).",
    ]
    assert [(u, s) for u, s, _ in parsear_fetch(lines)] == [(11, 500), (12, 600)]
    assert "Subject: Dos" in parsear_fetch(lines)[1][2]


class _Resp:
    def __init__(self, result="OK", lines=None):
        self.result, self.lines = result, lines or []


class ImapFalso:
    """Simula lo justo de aioimaplib: select, uid_search, uid fetch/copy/store/move, create."""

    def __init__(self, correos: dict[int, str]):
        self.correos = correos  # uid -> encabezados crudos
        self.ordenes: list[tuple] = []
        self.capabilities = {"MOVE", "UIDPLUS"}

    async def select(self, carpeta):
        self.ordenes.append(("select", carpeta))
        return _Resp()

    async def uid_search(self, criterio):
        self.ordenes.append(("search", criterio))
        if criterio == "ALL":
            uids = sorted(self.correos)
        else:
            # Acotación simplona: FROM "x" → correos cuyo From contiene x
            aguja = criterio.split('"')[1].lower()
            uids = [u for u, h in self.correos.items() if aguja in h.lower()]
        return _Resp(
            lines=[" ".join(str(u) for u in uids).encode(), b"Search completed."]
        )

    async def uid(self, orden, uids, *args):
        self.ordenes.append(("uid", orden, uids, *args))
        if orden == "fetch":
            lines = []
            for u in uids.split(","):
                lines.append(
                    f"1 FETCH (UID {u} RFC822.SIZE 1000 BODY[HEADER.FIELDS (FROM)] {{1}}".encode()
                )
                lines.append(self.correos[int(u)].encode())
                lines.append(b")")
            return _Resp(lines=lines)
        if orden == "move":
            return _Resp(lines=[b"OK [COPYUID 1 1 1] Move completed."])
        return _Resp()

    async def create(self, carpeta):
        self.ordenes.append(("create", carpeta))
        return _Resp()


CORREOS = {
    1: "From: Direccion <direccion@example.org>\r\nTo: yo@example.org\r\nSubject: Acta\r\n\r\n",
    2: "From: otro@example.org\r\nTo: yo@example.org\r\nCc: direccion@example.org\r\nSubject: Copia\r\n\r\n",
    3: "From: cursos@example.org\r\nTo: yo@example.org\r\nSubject: Curso\r\n\r\n",
}


@pytest.mark.asyncio
async def test_uids_que_cumplen_anyof_y_allof():
    imap = ImapFalso(CORREOS)
    regla = FilterRule(
        name="María Jesús",
        match="anyof",
        conditions=[
            c("from", "contains", "direccion@example.org"),
            c("recipients", "contains", "direccion@example.org"),
        ],
        actions=[FilterAction(type="move", value="INBOX.Maria")],
    )
    assert await uids_que_cumplen(imap, regla, Resultado("INBOX")) == [1, 2]
    regla.match = "allof"
    assert await uids_que_cumplen(imap, regla, Resultado("INBOX")) == []


@pytest.mark.asyncio
async def test_aplicar_mueve_y_marca_y_omite_reenvio():
    imap = ImapFalso(CORREOS)
    regla = FilterRule(
        name="Cursos",
        conditions=[c("from", "contains", "cursos@example.org")],
        actions=[
            FilterAction(type="read"),
            FilterAction(type="forward", value="alguien@example.org"),
            FilterAction(type="move", value="INBOX.Cursos"),
        ],
    )
    r = await aplicar_regla_existentes(imap, regla, "INBOX")
    assert (
        r["coinciden"] == 1
        and r["leidos"] == 1
        and r["movidos"] == 1
        and r["destino"] == "INBOX.Cursos"
    )
    assert r["omitidas"] == ["reenviar a alguien@example.org"]
    assert ("uid", "store", "3", "+FLAGS", "(\\Seen)") in imap.ordenes
    assert ("uid", "move", "3", "INBOX.Cursos") in imap.ordenes
    # El movimiento va después de marcar
    assert imap.ordenes.index(
        ("uid", "store", "3", "+FLAGS", "(\\Seen)")
    ) < imap.ordenes.index(("uid", "move", "3", "INBOX.Cursos"))


@pytest.mark.asyncio
async def test_aplicar_sin_coincidencias_no_toca_nada():
    imap = ImapFalso(CORREOS)
    regla = FilterRule(
        name="Nada",
        conditions=[c("from", "contains", "nadie@example.org")],
        actions=[FilterAction(type="move", value="X")],
    )
    r = await aplicar_regla_existentes(imap, regla, "INBOX")
    assert r["coinciden"] == 0 and r["movidos"] == 0
    assert not [
        o for o in imap.ordenes if o[0] == "uid" and o[1] in ("move", "store", "copy")
    ]


@pytest.mark.asyncio
async def test_eliminar_va_a_la_papelera():
    imap = ImapFalso(CORREOS)
    regla = FilterRule(
        name="Fuera",
        conditions=[c("from", "contains", "otro@example.org")],
        actions=[FilterAction(type="delete")],
    )
    r = await aplicar_regla_existentes(imap, regla, "INBOX")
    assert r["papelera"] == 1 and r["destino"] == "Trash"
    assert ("uid", "move", "2", "Trash") in imap.ordenes
