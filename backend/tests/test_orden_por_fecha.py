"""La bandeja se ordena por fecha, no por UID.

Antecedente (15/09/2026): tras migrar invertiagro.com y maquitaturismo.com desde Zimbra, la
gente decía que «no estaban los correos después del 27 de marzo». Estaban todos: el listado
caía al orden por UID porque aioimaplib rechaza `UID SORT` y la excepción se ignoraba. En un
buzón migrado en dos pasadas el UID no sigue la fecha, así que abril–agosto quedaban al final.

Estas pruebas vigilan que el SORT se envíe como manda el protocolo y que su respuesta se lea
bien; y que, si el servidor no puede ordenar, se siga sin romper nada.
"""

import asyncio

import pytest

from app.mail.clients import imap_sort


def test_lee_respuesta_sort_con_y_sin_asterisco():
    lineas = [b"* SORT 2980 2978 2979 602 601", b"SORT 10 9", b"Sort completed (0.001 secs)."]
    assert imap_sort.parse_sort_lines(lineas) == [2980, 2978, 2979, 602, 601, 10, 9]


def test_respuesta_vacia_da_lista_vacia():
    assert imap_sort.parse_sort_lines([b"* SORT", b"Sort completed."]) == []


class _Resp:
    def __init__(self, result, lines):
        self.result = result
        self.lines = lines


class _Proto:
    """Servidor de mentira: guarda la orden que se le envía y responde lo que se le diga."""

    def __init__(self, resp):
        self.resp = resp
        self.enviado = None
        self.loop = asyncio.get_event_loop()
        self._n = 0

    def new_tag(self):
        self._n += 1
        return f"T{self._n}"

    async def execute(self, cmd):
        self.enviado = str(cmd)
        if isinstance(self.resp, Exception):
            raise self.resp
        return self.resp


class _Imap:
    timeout = 5

    def __init__(self, proto):
        self.protocol = proto


@pytest.mark.asyncio
async def test_envia_uid_sort_reverse_date_por_omision():
    proto = _Proto(_Resp("OK", [b"* SORT 3 1 2", b"Sort completed."]))
    uids = await imap_sort.uid_sort(_Imap(proto), ["ALL"])
    assert uids == [3, 1, 2]
    assert proto.enviado == "T1 UID SORT (REVERSE DATE) UTF-8 ALL"


@pytest.mark.asyncio
async def test_respeta_criterios_de_busqueda():
    proto = _Proto(_Resp("OK", [b"* SORT 7"]))
    await imap_sort.uid_sort(_Imap(proto), ["SINCE", "01-Mar-2026", "FROM", '"ana"'])
    assert proto.enviado.endswith('UID SORT (REVERSE DATE) UTF-8 SINCE 01-Mar-2026 FROM "ana"')


@pytest.mark.asyncio
async def test_si_el_servidor_no_ordena_devuelve_none_sin_lanzar():
    assert await imap_sort.uid_sort(_Imap(_Proto(_Resp("NO", []))), ["ALL"]) is None
    assert await imap_sort.uid_sort(_Imap(_Proto(RuntimeError("caído"))), ["ALL"]) is None
