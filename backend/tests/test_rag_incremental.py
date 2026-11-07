"""RAG de todas las carpetas: incremental, cambio de UIDVALIDITY y límite por ejecución.

Se simula Dovecot (FakeIMAP con respuestas como las entrega aioimaplib) y el almacén en
memoria, para probar el recorrido completo de app.rag.indexador sin servidor.
"""

import asyncio

import pytest

from app.rag import almacen, indexador, plan, run, texto

# --- Decisiones puras ------------------------------------------------------------------------


def test_accion_por_carpeta():
    actual = {"uidvalidity": 7, "uidnext": 100, "mensajes": 50}
    assert plan.accion(None, actual, 2) == plan.REVISAR
    completa = {
        "uidvalidity": 7,
        "uidnext": 100,
        "mensajes": 50,
        "completa": True,
        "formato": 2,
    }
    assert plan.accion(completa, actual, 2) == plan.SALTAR
    assert plan.accion({**completa, "uidvalidity": 6}, actual, 2) == plan.REINICIAR
    assert (
        plan.accion({**completa, "uidnext": 90}, actual, 2) == plan.REVISAR
    )  # llegó correo
    assert (
        plan.accion({**completa, "mensajes": 51}, actual, 2) == plan.REVISAR
    )  # se borró uno
    assert plan.accion({**completa, "completa": False}, actual, 2) == plan.REVISAR
    assert plan.accion({**completa, "formato": 1}, actual, 2) == plan.REVISAR


def test_pendientes_nuevos_primero_y_borrados():
    indexados = {
        1: 2,
        2: 1,
        3: 2,
        9: 2,
    }  # 2 en formato viejo; 9 ya no está en el servidor
    por_hacer, borrar = plan.pendientes([1, 2, 3, 4, 5], indexados, 2)
    assert por_hacer == [5, 4, 2]
    assert borrar == [9]


def test_presupuesto_y_cupo():
    reloj = [0.0]
    p = plan.Presupuesto.con_minutos(limite=10, minutos=1, reloj=lambda: reloj[0])
    assert plan.cupo(p, 4, 1) == 3
    p.consumir(8)
    assert plan.cupo(p, 0, 0) == 2 and not p.agotado()
    reloj[0] = 61
    assert p.vencido() and p.agotado()
    assert plan.cupo(plan.Presupuesto(), 0, 0) is None


# --- Simulación de Dovecot y del almacén --------------------------------------------------------


class Resp:
    def __init__(self, result, lines):
        self.result, self.lines = result, lines


class FakeIMAP:
    """Buzón: {nombre: {"uidvalidity": int, "uids": [..], "flags": [..]}}."""

    def __init__(self, buzon):
        self.buzon = buzon
        self.abierta = None
        self.ordenes = []
        self.en_vuelo = False
        self.protocol = type("P", (), {"state": "AUTH"})()

    async def list(self, ref, patron):
        lineas = [
            f'LIST ({" ".join(d.get("flags", ["\\HasNoChildren"]))}) "." "{n}"'.encode()
            for n, d in self.buzon.items()
        ]
        return Resp("OK", lineas + [b"List completed."])

    async def examine(self, nombre):
        n = nombre.strip('"')
        self.ordenes.append(("EXAMINE", n))
        d = self.buzon.get(n)
        if d is None:
            return Resp("NO", [b"Mailbox doesn't exist"])
        self.abierta = n
        return Resp(
            "OK",
            [
                f"{len(d['uids'])} EXISTS".encode(),
                f"OK [UIDVALIDITY {d['uidvalidity']}] UIDs valid".encode(),
                f"OK [UIDNEXT {max(d['uids'], default=0) + 1}] Predicted next UID".encode(),
                b"[READ-ONLY] Examine completed.",
            ],
        )

    async def uid_search(self, *criterios, charset=None):
        assert self.protocol.state == "SELECTED"
        self.ordenes.append(("SEARCH", self.abierta))
        uids = " ".join(map(str, self.buzon[self.abierta]["uids"]))
        return Resp("OK", [f"SEARCH {uids}".encode(), b"Search completed."])

    async def uid(self, orden, conjunto, items):
        assert orden == "fetch" and self.protocol.state == "SELECTED"
        assert not self.en_vuelo, "dos órdenes a la vez en la misma conexión IMAP"
        self.en_vuelo = True
        await asyncio.sleep(
            0
        )  # deja correr los embeddings mientras «llega» la respuesta
        self.en_vuelo = False
        assert "PEEK" in items  # nunca se marca nada como leído
        self.ordenes.append(("FETCH", self.abierta, items))
        lineas = []
        for i, u in enumerate(int(x) for x in conjunto.split(",")):
            if u not in self.buzon[self.abierta]["uids"]:
                continue
            if "BODYSTRUCTURE" in items:
                cab = f"From: a{u}@x.org\r\nSubject: Asunto {u}\r\n\r\n".encode()
                lineas += [
                    f'{i + 1} FETCH (UID {u} BODYSTRUCTURE ("TEXT" "PLAIN" ("CHARSET" "utf-8") NIL NIL "7BIT" 20 1 NIL NIL NIL NIL) BODY[HEADER.FIELDS (FROM TO CC SUBJECT DATE)] {{{len(cab)}}}'.encode(),
                    bytearray(cab),
                    b")",
                ]
            else:
                cuerpo = f"Cuerpo del correo {u} en {self.abierta}".encode()
                lineas += [
                    f"{i + 1} FETCH (UID {u} BODY[1]<0> {{{len(cuerpo)}}}".encode(),
                    bytearray(cuerpo),
                    b")",
                ]
        return Resp("OK", lineas + [b"Fetch completed."])

    async def logout(self):
        return Resp("OK", [])


class FakeAlmacen:
    def __init__(self):
        self.filas = {}  # (folder, uid) -> (contenido, formato)
        self.estados = {}

    def instalar(self, mp):
        async def nada(db):
            return None

        async def formatos(db, u, f):
            return {uid: fm for (ff, uid), (_, fm) in self.filas.items() if ff == f}

        async def guardar_lote(db, u, f, filas):
            for uid, _a, _r, contenido, _e, fm in filas:
                self.filas[(f, int(uid))] = (contenido, fm)

        async def borrar_uids(db, u, f, uids):
            for x in uids:
                self.filas.pop((f, int(x)), None)

        async def borrar_carpeta(db, u, f):
            for k in [k for k in self.filas if k[0] == f]:
                del self.filas[k]
            self.estados.pop(f, None)

        async def borrar_ausentes(db, u, vigentes):
            for k in [k for k in self.filas if k[0] not in vigentes]:
                del self.filas[k]

        async def estado(db, u, f):
            return self.estados.get(f)

        async def guardar_estado(db, u, f, info, indexados, completa, formato):
            self.estados[f] = {
                **info,
                "indexados": indexados,
                "completa": completa,
                "formato": formato,
            }

        async def contar(db, u, f):
            return sum(1 for k in self.filas if k[0] == f)

        for nombre, fn in locals().items():
            if nombre not in ("self", "mp") and callable(fn):
                mp.setattr(
                    almacen, "asegurar_esquema" if nombre == "nada" else nombre, fn
                )

    def carpeta(self, f):
        return sorted(uid for ff, uid in self.filas if ff == f)


async def _embed(t):
    return [0.1] * 3


def _prog():
    return {"leidos": 0, "indexed": 0, "errores": 0}


async def _indexar(imap, limite_buzon=0, presupuesto=None, embed_fn=_embed):
    async def conectar():
        return imap

    async def publicar():
        return None

    prog = _prog()
    r = await indexador.indexar_buzon(
        None,
        "ana@example.org",
        conectar,
        prog,
        publicar,
        limite_buzon,
        presupuesto or plan.Presupuesto(),
        embed_fn=embed_fn,
        cfg={"tanda": 20, "cuerpo_chars": 1500, "pausa_s": 0},
    )
    return r, prog


def _buzon():
    return {
        "INBOX": {
            "uidvalidity": 1,
            "uids": list(range(1, 51)),
            "flags": ["\\HasChildren"],
        },
        "INBOX.Bandeja entrada Respaldo": {
            "uidvalidity": 5,
            "uids": list(range(1, 31)),
        },
        "Sent": {"uidvalidity": 2, "uids": list(range(1, 21)), "flags": ["\\Sent"]},
        "Trash": {"uidvalidity": 3, "uids": [1, 2, 3], "flags": ["\\Trash"]},
        "Junk": {"uidvalidity": 4, "uids": [1, 2]},
        "Drafts": {"uidvalidity": 6, "uids": [1]},
    }


@pytest.fixture
def mem(monkeypatch):
    a = FakeAlmacen()
    a.instalar(monkeypatch)
    return a


async def test_indexa_todas_las_carpetas_salvo_excluidas_con_cuerpo_y_carpeta(mem):
    imap = FakeIMAP(_buzon())
    r, prog = await _indexar(imap)
    assert r == {"completo": True, "carpetas": 3}
    assert mem.carpeta("INBOX") == list(range(1, 51))
    assert mem.carpeta("Sent") == list(range(1, 21))
    assert len(mem.carpeta("INBOX.Bandeja entrada Respaldo")) == 30
    assert (
        not mem.carpeta("Trash")
        and not mem.carpeta("Junk")
        and not mem.carpeta("Drafts")
    )
    assert not [o for o in imap.ordenes if o[1] in ("Trash", "Junk", "Drafts")]
    contenido, formato = mem.filas[("Sent", 7)]
    assert formato == texto.FORMATO
    assert contenido.startswith("Carpeta: Enviados | De: a7@x.org | Asunto: Asunto 7")
    assert contenido.endswith("Cuerpo del correo 7 en Sent")
    assert prog["indexed"] == 100 and prog["carpetas_hechas"] == 3


async def test_segunda_pasada_sin_cambios_no_pide_uids_y_luego_solo_lo_nuevo(mem):
    buzon = _buzon()
    await _indexar(FakeIMAP(buzon))
    imap = FakeIMAP(buzon)
    r, prog = await _indexar(imap)
    assert prog["indexed"] == 0
    assert not [o for o in imap.ordenes if o[0] in ("SEARCH", "FETCH")]  # todo saltado
    buzon["Sent"]["uids"] += [21, 22]  # llegan dos enviados
    buzon["INBOX"]["uids"].remove(10)  # y se borra uno de la entrada
    imap = FakeIMAP(buzon)
    r, prog = await _indexar(imap)
    assert prog["indexed"] == 2
    assert mem.carpeta("Sent")[-2:] == [21, 22]
    assert 10 not in mem.carpeta("INBOX")
    pedidos = [o for o in imap.ordenes if o[0] == "FETCH"]
    assert all(o[1] == "Sent" for o in pedidos)


async def test_cambio_de_uidvalidity_reindexa_la_carpeta(mem):
    buzon = _buzon()
    await _indexar(FakeIMAP(buzon))
    buzon["INBOX.Bandeja entrada Respaldo"] = {"uidvalidity": 99, "uids": [500, 501]}
    r, prog = await _indexar(FakeIMAP(buzon))
    assert mem.carpeta("INBOX.Bandeja entrada Respaldo") == [500, 501]
    assert mem.estados["INBOX.Bandeja entrada Respaldo"]["uidvalidity"] == 99
    assert prog["indexed"] == 2


async def test_limite_por_ejecucion_avanza_y_retoma_del_mas_reciente(mem):
    buzon = _buzon()
    r, prog = await _indexar(FakeIMAP(buzon), presupuesto=plan.Presupuesto(limite=30))
    assert r["completo"] is False and prog["indexed"] == 30
    assert mem.carpeta("INBOX") == list(range(21, 51))  # los 30 más recientes primero
    assert mem.estados["INBOX"]["completa"] is False
    r, prog = await _indexar(FakeIMAP(buzon), limite_buzon=40)
    assert prog["indexed"] == 40 and r["completo"] is False
    r, prog = await _indexar(FakeIMAP(buzon))
    assert r["completo"] is True
    assert len(mem.filas) == 100  # sin duplicados ni huecos


async def test_hora_tope_corta_entre_tandas_y_la_carpeta_queda_a_medias(mem):
    reloj = [0.0]
    presupuesto = plan.Presupuesto.con_minutos(minutos=1, reloj=lambda: reloj[0])

    async def embed_lento(t):
        reloj[0] += 3  # 20 correos por tanda: la primera tanda llega a los 60 s
        return [0.1]

    r, prog = await _indexar(
        FakeIMAP(_buzon()), presupuesto=presupuesto, embed_fn=embed_lento
    )
    assert r["completo"] is False
    assert prog["indexed"] == 20 and mem.carpeta("INBOX") == list(range(31, 51))
    assert mem.estados["INBOX"]["completa"] is False


async def test_correos_del_formato_anterior_se_rehacen(mem):
    for uid in range(1, 51):
        mem.filas[("INBOX", uid)] = (
            "De: x | Asunto: y | ",
            1,
        )  # indexado por el código viejo
    r, prog = await _indexar(FakeIMAP(_buzon()))
    assert all(fm == texto.FORMATO for _, fm in mem.filas.values())
    assert mem.filas[("INBOX", 1)][0].startswith("Carpeta: Bandeja de entrada")


async def test_carpeta_borrada_o_ahora_excluida_sale_del_indice(mem):
    mem.filas[("Trash", 1)] = ("viejo", 2)
    mem.filas[("Carpeta que ya no existe", 4)] = ("viejo", 2)
    await _indexar(FakeIMAP(_buzon()))
    assert not mem.carpeta("Trash") and not mem.carpeta("Carpeta que ya no existe")


async def test_embeddings_caidos_detiene_sin_marcar_completa(mem):
    async def sin_ia(t):
        return []

    with pytest.raises(indexador.EmbeddingsCaidos):
        await _indexar(FakeIMAP(_buzon()), embed_fn=sin_ia)
    assert not mem.filas
    assert not mem.estados.get("INBOX", {}).get("completa")


# --- Rondas de la tarea nocturna ----------------------------------------------------------------


async def test_rondas_reparten_entre_buzones_y_respetan_el_tope():
    quedan = {"a": 12000, "b": 3000, "c": 0}
    llamadas = []

    async def ingesta(db, u, limit, redis, presupuesto):
        n = min(
            limit, quedan[u], presupuesto.restante()
        )  # como plan.cupo en el indexador
        quedan[u] -= n
        presupuesto.consumir(n)
        llamadas.append((u, n))
        return {"indexed": n, "total": 0, "incompleto": quedan[u] > 0}

    r = await run.todos(
        None,
        ["a", "b", "c"],
        ingesta,
        plan.Presupuesto(limite=14000),
        5000,
        registrar=lambda m: None,
    )
    assert llamadas[:3] == [
        ("a", 5000),
        ("b", 3000),
        ("c", 0),
    ]  # todos avanzan en la ronda 1
    assert quedan == {"a": 1000, "b": 0, "c": 0}  # se paró en el límite de 14.000
    assert r["indexados"] == 14000 and r["pendientes"] == 1
