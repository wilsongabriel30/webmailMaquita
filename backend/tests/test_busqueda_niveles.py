"""Resultados de la búsqueda por niveles: lo exacto delante, con tope de tiempo en todo."""

import asyncio
import json

import pytest

from app.mail.clients import imap_client
from app.mail.services import busqueda_niveles as bn
from app.mail.services import message_service


class _Resp:
    def __init__(self, lines, result="OK"):
        self.result, self.lines = result, lines


class _Transporte:
    cerrado = False

    def close(self):
        self.cerrado = True


class _Protocolo:
    def __init__(self):
        self.transport = _Transporte()


class _Imap:
    """IMAP de mentira: `encabezado` son los UIDs del nivel 1 según el índice."""

    def __init__(
        self, encabezado=(), correos=None, tarda_busqueda=0.0, tarda_fetch=0.0
    ):
        self.encabezado = list(encabezado)
        self.correos = correos or {}  # uid -> (asunto, texto)
        self.tarda_busqueda, self.tarda_fetch = tarda_busqueda, tarda_fetch
        self.busquedas, self.fetches = [], []
        self.protocol = _Protocolo()

    async def select(self, carpeta):
        return _Resp([])

    async def uid_search(self, *criterio, charset="utf-8"):
        self.busquedas.append(" ".join(criterio))
        await asyncio.sleep(self.tarda_busqueda)
        return _Resp(
            [" ".join(str(u) for u in self.encabezado).encode(), b"Search completed."]
        )

    async def uid(self, orden, conjunto, campos):
        self.fetches.append((conjunto, campos))
        await asyncio.sleep(self.tarda_fetch)
        lineas = []
        for n, uid in enumerate(int(u) for u in conjunto.split(",")):
            asunto, texto = self.correos.get(uid, ("", ""))
            cab = (
                f"Subject: {asunto}\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n"
            )
            lineas.append(
                f"{n + 1} FETCH (UID {uid} BODY[HEADER.FIELDS (SUBJECT)] {{{len(cab)}}}".encode()
            )
            lineas.append(bytearray(cab.encode()))
            if "TEXT" in campos:
                lineas.append(f" BODY[TEXT]<0> {{{len(texto.encode())}}}".encode())
                lineas.append(bytearray(texto.encode()))
            lineas.append(b")")
        lineas.append(b"Fetch completed.")
        return _Resp(lineas)


class _Redis:
    def __init__(self):
        self.datos = {}

    async def get(self, clave):
        return self.datos.get(clave)

    async def set(self, clave, valor, ex=None):
        self.datos[clave] = valor

    async def sadd(self, *a):
        return 1

    async def expire(self, *a):
        return 1


@pytest.fixture(autouse=True)
def _sin_pausas():
    bn._en_pausa.clear()
    yield
    bn._en_pausa.clear()


def _plan(consulta, **kw):
    return bn.plan(consulta, False, True, kw.pop("direcciones", ()), **kw)


# --- cuándo hay niveles ---------------------------------------------------------------


def test_una_sola_palabra_se_queda_como_esta():
    assert _plan("factura") is None
    assert _plan("de:ana factura") is None


def test_sin_indice_de_texto_no_hay_niveles():
    """Sin índice, repetir una búsqueda en el cuerpo (más de un minuto) sería peor que no ordenar."""
    assert bn.plan("fernando pacheco", False, False) is None
    assert bn.plan("fernando pacheco", True, False) is None
    assert bn.plan("fernando pacheco", True, True) is not None


def test_varias_palabras_nivel_1_solo_en_encabezados():
    p = _plan("fernando pacheco")
    t = " ".join(p.criterio_encabezado)
    assert "BODY" not in t and p.exactos == ()
    for campo in ("FROM", "TO", "CC", "SUBJECT"):
        assert f'{campo} "fernando"' in t and f'{campo} "pacheco"' in t


def test_el_nivel_1_incluye_a_la_persona_que_se_llama_asi():
    p = _plan("fernando pacheco", direcciones=["fpacheco@example.org"])
    t = " ".join(p.criterio_encabezado)
    assert 'FROM "fpacheco@example.org"' in t and 'CC "fpacheco@example.org"' in t


def test_los_operadores_acotan_tambien_el_nivel_1():
    p = _plan("fernando pacheco despues:2026-01-01 es:noleido")
    assert "SINCE" in p.criterio_encabezado and "UNSEEN" in p.criterio_encabezado


def test_un_valor_o_una_frase_se_comprueban_aunque_sea_un_solo_termino():
    assert _plan("205,6").exactos == ("205.6",)
    assert _plan("205.6").exactos == ("205.6",)
    assert _plan('"informe mensual"').exactos == ("informe mensual",)
    assert _plan("pago 1.250,00").exactos == ("1.250.00",)


# --- orden ----------------------------------------------------------------------------


def test_el_nivel_1_va_delante_y_cada_nivel_conserva_la_fecha():
    imap = _Imap(encabezado=[3, 7, 999])  # 999 no está en la lista: no se cuela
    orden, exactos = asyncio.run(
        bn.ordenar(imap, [9, 8, 7, 6, 5, 4, 3], _plan("fernando pacheco"))
    )
    assert orden == [7, 3, 9, 8, 6, 5, 4] and exactos == 2
    assert imap.fetches == [], "con palabras basta el índice: no se abre ningún correo"
    assert imap.busquedas[0].startswith("UID 3:9 "), "acotada a los UIDs de la lista"


def test_la_busqueda_del_nivel_1_se_acota_a_los_mas_recientes(monkeypatch):
    """Sin acotar, en «todas las carpetas» cada búsqueda costaba 3 s más."""
    assert bn.conjunto_de_uids([7, 1, 2, 3, 9, 10]) == "1:3,7,9:10"
    assert bn.conjunto_de_uids([5]) == "5"
    monkeypatch.setattr(bn, "MAX_ACOTADOS", 3)
    imap = _Imap(
        encabezado=[20, 18, 2]
    )  # el 2 es antiguo: queda fuera de lo que se mira
    orden, exactos = asyncio.run(
        bn.ordenar(imap, [20, 19, 18, 3, 2], _plan("ana factura"))
    )
    assert imap.busquedas[0].startswith("UID 18:20 ")
    assert orden == [20, 18, 19, 3, 2] and exactos == 2
    assert asyncio.run(bn.ordenar(imap, [], _plan("ana factura"))) == ([], 0)


def test_valor_exacto_en_el_asunto_o_en_el_texto():
    correos = {
        9: ("Pago", "abono de 205157 el día 6"),
        8: ("Pago", "el valor es 205,6 USD"),
        7: ("Cuota 205.6", ""),
        6: ("Cuota 205.65", "nada"),
        5: ("Otro", "total 205,60"),
    }
    imap = _Imap(encabezado=[7, 6], correos=correos)
    orden, exactos = asyncio.run(bn.ordenar(imap, [9, 8, 7, 6, 5], _plan("205,6")))
    assert orden == [8, 7, 5, 9, 6] and exactos == 3
    assert (
        "TEXT" not in imap.fetches[0][1]
    ), "los del asunto se comprueban sin abrir el cuerpo"
    assert "BODY.PEEK[TEXT]<0." in imap.fetches[1][1]
    assert "7" not in imap.fetches[1][0].split(
        ","
    ), "lo ya comprobado no se vuelve a leer"


def test_frase_entre_comillas_primero_la_frase_tal_cual():
    correos = {
        3: ("Informe mensual de ventas", ""),
        2: ("Informe", "el cierre mensual va adjunto"),
        1: ("Hola", "adjunto el informe mensual"),
    }
    imap = _Imap(encabezado=[3], correos=correos)
    orden, exactos = asyncio.run(
        bn.ordenar(imap, [3, 2, 1], _plan('"informe mensual"'))
    )
    assert orden == [3, 1, 2] and exactos == 2


def test_solo_se_comprueban_los_mas_recientes(monkeypatch):
    monkeypatch.setattr(bn, "MAX_TEXTOS", 4)
    monkeypatch.setattr(bn, "TANDA_TEXTOS", 2)
    correos = {u: ("x", "valor 205,6") for u in range(1, 11)}
    imap = _Imap(correos=correos)
    uids = list(range(10, 0, -1))
    orden, exactos = asyncio.run(bn.ordenar(imap, uids, _plan("205,6")))
    assert exactos == 4 and orden == uids
    assert [f[0] for f in imap.fetches] == ["10,9", "8,7"]


def test_presupuesto_agotado_lo_no_comprobado_queda_en_el_nivel_2(monkeypatch):
    monkeypatch.setattr(bn, "PRESUPUESTO_S", 0.05)
    monkeypatch.setattr(bn, "TANDA_TEXTOS", 1)
    correos = {u: ("x", "valor 205,6") for u in range(1, 8)}
    imap = _Imap(correos=correos, tarda_fetch=0.04)
    orden, exactos = asyncio.run(
        bn.ordenar(imap, [7, 6, 5, 4, 3, 2, 1], _plan("205,6"))
    )
    assert 1 <= exactos < 7, "se detiene al agotar el presupuesto, sin error"
    assert sorted(orden) == [1, 2, 3, 4, 5, 6, 7], "no se pierde ningún resultado"
    assert not imap.protocol.transport.cerrado


# --- topes de tiempo ------------------------------------------------------------------


def test_busqueda_colgada_cierra_la_conexion_y_pausa_los_niveles(monkeypatch):
    monkeypatch.setattr(bn, "TOPE_BUSQUEDA_S", 0.05)
    imap = _Imap(tarda_busqueda=5)
    p = _plan("fernando pacheco", clave="u|INBOX|fernando pacheco")
    with pytest.raises(bn.NivelesSinTiempo) as error:
        asyncio.run(bn.ordenar(imap, [3, 2, 1], p))
    from app.mail.clients.imap_pool import es_conexion_caida

    assert es_conexion_caida(
        error.value
    ), "el listado lo reintenta con una conexión nueva"
    assert imap.protocol.transport.cerrado and imap.conexion_sucia
    assert _plan("fernando pacheco", clave="u|INBOX|fernando pacheco") is None
    assert _plan("fernando pacheco", clave="otra|INBOX|fernando pacheco") is not None


def test_lectura_colgada_cierra_la_conexion(monkeypatch):
    monkeypatch.setattr(bn, "TOPE_TANDA_S", 0.05)
    imap = _Imap(correos={1: ("x", "205,6")}, tarda_fetch=5)
    with pytest.raises(bn.NivelesSinTiempo):
        asyncio.run(bn.ordenar(imap, [1], _plan("205,6", clave="k")))
    assert imap.protocol.transport.cerrado


def test_respuesta_de_error_deja_la_lista_como_estaba():
    imap = _Imap()

    async def falla(*a, **k):
        return _Resp([], "NO")

    imap.uid_search = falla
    assert asyncio.run(bn.ordenar(imap, [3, 2, 1], _plan("a1 b2"))) == ([3, 2, 1], 0)


# --- lectura de la respuesta de FETCH -----------------------------------------------------


def test_partes_de_fetch_con_uid_al_final_y_literal_vacio():
    lineas = [
        b"1 FETCH (BODY[HEADER.FIELDS (SUBJECT)] {12}",
        bytearray(b"Subject: a\r\n"),
        b" BODY[TEXT]<0> {0}",
        bytearray(b""),
        b" UID 41)",
        b"2 FETCH (UID 42 BODY[HEADER.FIELDS (SUBJECT)] {12}",
        bytearray(b"Subject: b\r\n"),
        b" BODY[TEXT]<0> {4}",
        bytearray(b"hola"),
        b")",
        b"Fetch completed (0.001 + 0.000 secs).",
    ]
    assert bn.partes_de_fetch(lineas) == {
        41: (b"Subject: a\r\n", b""),
        42: (b"Subject: b\r\n", b"hola"),
    }


# --- listado completo, caché y respuesta ----------------------------------------------


def _con_sort(monkeypatch, uids):
    async def uid_sort(imap, criterio):
        imap.ordenes = getattr(imap, "ordenes", 0) + 1
        return list(uids)

    monkeypatch.setattr(imap_client, "uid_sort", uid_sort)
    monkeypatch.setattr(imap_client, "cuenta_indexada", lambda u: True)


def test_listado_devuelve_exactos_y_guarda_la_lista_ya_ordenada(monkeypatch):
    _con_sort(monkeypatch, [9, 8, 7, 6, 5])
    imap, redis = _Imap(encabezado=[6, 8]), _Redis()

    def pide(pagina):
        return asyncio.run(
            imap_client.list_message_uids(
                imap,
                "INBOX",
                pagina,
                2,
                "ana factura",
                redis=redis,
                username="u@example.org",
                por_niveles=True,
            )
        )

    r1 = pide(1)
    assert r1["uids"] == [8, 6] and r1["exactos"] == 2 and r1["total"] == 5
    (clave,) = redis.datos
    assert clave.startswith(
        bn.PREFIJO_CACHE
    ), "clave propia: no se mezcla con las listas sin niveles"
    assert json.loads(redis.datos[clave]) == {"uids": [8, 6, 9, 7, 5], "exactos": 2}
    r2 = pide(2)
    assert r2["uids"] == [9, 7] and r2["exactos"] == 2
    assert (
        imap.ordenes == 1 and len(imap.busquedas) == 1
    ), "la segunda página sale de la memoria"


def test_listado_sin_pedir_niveles_o_de_una_palabra_no_cambia(monkeypatch):
    _con_sort(monkeypatch, [9, 8, 7])
    for consulta, por_niveles in (
        ("ana factura", False),
        ("factura", True),
        ("", True),
    ):
        imap, redis = _Imap(encabezado=[7]), _Redis()
        r = asyncio.run(
            imap_client.list_message_uids(
                imap,
                "INBOX",
                1,
                50,
                consulta,
                redis=redis,
                username="u@example.org",
                por_niveles=por_niveles,
            )
        )
        assert r == {"uids": [9, 8, 7], "total": 3, "page": 1, "per_page": 50}
        assert imap.busquedas == []
        (clave,) = redis.datos
        assert clave.startswith("uids:") and json.loads(redis.datos[clave]) == [9, 8, 7]


def test_tras_agotar_el_tiempo_el_reintento_sale_sin_niveles(monkeypatch):
    _con_sort(monkeypatch, [9, 8, 7])
    monkeypatch.setattr(bn, "TOPE_BUSQUEDA_S", 0.05)

    def pide(imap):
        return asyncio.run(
            imap_client.list_message_uids(
                imap,
                "INBOX",
                1,
                50,
                "ana factura",
                username="u@example.org",
                por_niveles=True,
            )
        )

    with pytest.raises(bn.NivelesSinTiempo):
        pide(_Imap(tarda_busqueda=5))
    nueva = _Imap(tarda_busqueda=5)
    assert pide(nueva) == {"uids": [9, 8, 7], "total": 3, "page": 1, "per_page": 50}
    assert nueva.busquedas == []


def test_anotar_marca_cada_mensaje_segun_su_lugar_en_la_lista():
    mensajes = [
        {"uid": 5},
        {"uid": 7},
        {"uid": 6},
    ]  # la página 2 de una lista con 4 exactos
    bn.anotar(mensajes, [7, 6, 5], desde=3, exactos=4)
    assert {m["uid"]: m["coincidencia"] for m in mensajes} == {
        7: "exacta",
        6: "contenido",
        5: "contenido",
    }


def test_la_respuesta_de_la_lista_anade_campos_sin_quitar_ninguno(monkeypatch):
    async def uids(*a, **k):
        assert k["por_niveles"] is True
        return {"uids": [8, 9], "total": 2, "page": 1, "per_page": 50, "exactos": 1}

    async def cabeceras(imap, lista):
        return [
            {
                "uid": u,
                "flags": [],
                "size": 1,
                "snippet": "",
                "has_attachments": False,
                "internal_date": None,
                "raw_headers": "Subject: hola\r\nFrom: a@example.org\r\n",
            }
            for u in lista
        ]

    async def adjuntos(*a, **k):
        return {}

    monkeypatch.setattr(message_service, "list_message_uids", uids)
    monkeypatch.setattr(message_service, "fetch_message_headers", cabeceras)
    monkeypatch.setattr(message_service, "adjuntos_por_uid", adjuntos)
    r = asyncio.run(
        message_service.list_messages(
            None, "INBOX", 1, 50, "ana factura", por_niveles=True
        )
    )
    assert {"messages", "total", "page", "per_page"} <= set(r) and r[
        "total_exactos"
    ] == 1
    assert [(m["uid"], m["coincidencia"]) for m in r["messages"]] == [
        (8, "exacta"),
        (9, "contenido"),
    ]


def test_sin_niveles_la_respuesta_es_la_de_siempre(monkeypatch):
    async def uids(*a, **k):
        return {"uids": [], "total": 0, "page": 1, "per_page": 50}

    monkeypatch.setattr(message_service, "list_message_uids", uids)
    r = asyncio.run(message_service.list_messages(None, "INBOX", 1, 50, "factura"))
    assert r == {"messages": [], "total": 0, "page": 1, "per_page": 50}
