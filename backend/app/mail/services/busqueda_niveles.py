"""Resultados de la búsqueda por niveles: primero lo que coincide de verdad (13/11/2026).

Con índice de texto, cada palabra puede estar en cualquier parte del correo. Eso encuentra mucho,
pero «fernando pacheco» traía 502 correos y de los 50 primeros solo 19 eran de esa persona: el
resto tenía las dos palabras perdidas en el texto. Y «205,6» traía 2 534 correos con «205…».

La lista no pierde nada; se ordena en dos niveles, cada uno por fecha (recientes primero):

1. Coincidencia exacta: TODAS las palabras están en el encabezado (remitente, para, copia o
   asunto), o el correo es de/para la persona que se llama así. Si lo buscado es un valor
   («205,6») o una frase entre comillas, además se COMPRUEBA que aparece tal cual en el asunto o
   en el texto, porque el índice no distingue un valor de sus trozos.
2. El resto: coincidencias solo en el contenido, y lo que no dio tiempo a comprobar.

Coste, medido en un buzón de 209 847 mensajes: la búsqueda del nivel 1 va por el índice y se
acota a los UIDs que ya están en la lista. Así cuesta de 0,1 a 1,7 s; sin acotar, en «todas las
carpetas» eran 3 s más por búsqueda (la carpeta virtual recorre sus 65 carpetas cada vez). Para
que el conjunto de UIDs quepa en una orden se miran los `MAX_ACOTADOS` resultados más recientes;
en una lista más larga, los más antiguos quedan en el nivel 2.
Comprobar el texto obliga a abrir cada correo: 2 s los 200 más recientes si están en la memoria
del servidor, pero 80-130 ms por correo si hay que ir al disco. Por eso la comprobación tiene un
presupuesto de tiempo, va de lo más reciente a lo más antiguo y se detiene al agotarlo: lo no
comprobado se queda en el nivel 2 y la siguiente búsqueda llega más lejos.

Ninguna orden IMAP de aquí puede quedarse esperando: todas llevan tope. Si una lo agota, la
conexión se cierra en el acto (no vuelve al fondo de conexiones), esa búsqueda queda unos minutos
sin niveles y se avisa a quien llama con `NivelesSinTiempo`, que se trata como una conexión caída:
la lista se pide otra vez por una conexión nueva y sale como siempre, sin niveles.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass

from app.mail import busqueda_exacta, busqueda_palabras

log = logging.getLogger(__name__)

TOPE_BUSQUEDA_S = 6.0  # la búsqueda del nivel 1 (acotada suele ser menos de 2 s)
MAX_ACOTADOS = 4000  # resultados más recientes entre los que se busca el nivel 1
TOPE_TANDA_S = 6.0  # una tanda de lectura atascada: se corta la conexión
PRESUPUESTO_S = 2.5  # todo lo que se comprueba abriendo correos (encabezados y texto)
PRESUPUESTO_ENCABEZADOS_S = 1.0  # de ese total, lo que pueden llevarse los encabezados
MAX_ENCABEZADOS = 100  # candidatos por encabezado cuyo asunto se comprueba
MAX_TEXTOS = 200  # candidatos más recientes cuyo texto se comprueba
TANDA_ENCABEZADOS = 25
TANDA_TEXTOS = 8
BYTES_DE_TEXTO = 32768  # principio del cuerpo que se lee de cada candidato
PAUSA_S = 300  # sin niveles para una búsqueda que agotó el tiempo
PREFIJO_CACHE = "uidsn:"  # clave propia: no se mezcla con las listas sin niveles

_CAMPOS_ENCABEZADO = "(UID BODY.PEEK[HEADER.FIELDS (SUBJECT FROM TO CC)])"
_CAMPOS_TEXTO = (
    "(UID BODY.PEEK[HEADER.FIELDS (SUBJECT CONTENT-TYPE CONTENT-TRANSFER-ENCODING)]"
    f" BODY.PEEK[TEXT]<0.{BYTES_DE_TEXTO}>)"
)
_RE_INICIO = re.compile(rb"^\d+ FETCH \(")
_RE_UID = re.compile(rb"\bUID (\d+)")
_en_pausa: dict[str, float] = {}


class NivelesSinTiempo(ConnectionError):
    """Una orden de los niveles agotó su tope y la conexión se cerró (closed)."""


@dataclass(frozen=True)
class Plan:
    """Lo que hace falta para ordenar una búsqueda por niveles."""

    criterio_encabezado: tuple[str, ...]
    exactos: tuple[str, ...] = ()
    clave: str = ""


def plan(
    consulta: str,
    buscar_en_contenido: bool,
    con_indice: bool,
    direcciones: tuple | list = (),
    clave: str = "",
) -> Plan | None:
    """El plan de niveles de una consulta, o `None` si debe quedarse como está.

    Se queda como está: una sola palabra, la búsqueda que acaba de agotar el tiempo y las
    cuentas sin índice de texto. Sin índice, o no se entra en el cuerpo (todo acierto es ya de
    encabezado) o la búsqueda en el cuerpo tarda más de un minuto, y repetirla porque los niveles
    agotaron su tope sería peor que no ordenar.
    """
    from app.mail.search_advanced import parse_search_query

    if not con_indice or not (consulta or "").strip():
        return None
    if _en_pausa.get(clave, 0) > time.monotonic():
        return None
    detalle: dict = {}
    criterio = parse_search_query(
        consulta,
        buscar_en_contenido=buscar_en_contenido,
        con_indice=con_indice,
        direcciones_nombre=direcciones,
        solo_encabezados=True,
        detalle=detalle,
    )
    terminos = busqueda_palabras.terminos(detalle.get("libres") or [])
    exactos = tuple(t for t in terminos if busqueda_exacta.es_exacto(t))
    if len(terminos) < 2 and not exactos:
        return None
    return Plan(tuple(criterio), exactos, clave)


def _pausar(clave: str) -> None:
    ahora = time.monotonic()
    if len(_en_pausa) > 500:
        for vieja in [k for k, v in _en_pausa.items() if v <= ahora]:
            _en_pausa.pop(vieja, None)
    if clave:
        _en_pausa[clave] = ahora + PAUSA_S


def _cortar(imap, plan_: Plan, motivo: str) -> NivelesSinTiempo:
    """Cierra YA la conexión con la orden a medias y deja la búsqueda un rato sin niveles."""
    setattr(imap, "conexion_sucia", True)
    try:
        imap.protocol.transport.close()
    except Exception:
        pass
    _pausar(plan_.clave)
    log.warning("busqueda_niveles: %s; conexión cerrada y búsqueda sin niveles", motivo)
    return NivelesSinTiempo("connection closed: " + motivo)


def conjunto_de_uids(uids: list[int]) -> str:
    """Los UIDs como conjunto IMAP con rangos: [1, 2, 3, 7] → «1:3,7»."""
    tramos: list[str] = []
    orden = sorted(set(uids))
    inicio = fin = orden[0]
    for u in orden[1:] + [None]:
        if u is not None and u == fin + 1:
            fin = u
            continue
        tramos.append(str(inicio) if inicio == fin else f"{inicio}:{fin}")
        if u is not None:
            inicio = fin = u
    return ",".join(tramos)


def _uids_de_busqueda(lineas) -> set[int]:
    uids: set[int] = set()
    for linea in lineas:
        if isinstance(linea, (bytes, bytearray)):
            linea = bytes(linea).decode("ascii", "replace")
        if "completed" in linea:
            continue
        uids.update(int(x) for x in linea.split() if x.isdigit())
    return uids


def partes_de_fetch(lineas) -> dict[int, tuple[bytes, bytes]]:
    """{uid: (cabeceras, texto)} de la respuesta de un FETCH con uno o dos literales por correo."""
    correos: dict[int, tuple[bytes, bytes]] = {}
    uid, cabeceras, texto, toca = 0, b"", b"", ""

    def cerrar() -> None:
        if uid:
            correos[uid] = (cabeceras, texto)

    for linea in lineas:
        if isinstance(linea, bytearray):  # un literal: lo anunció la línea anterior
            if toca == "texto":
                texto = bytes(linea)
            elif toca == "cabeceras":
                cabeceras = bytes(linea)
            toca = ""
            continue
        if not isinstance(linea, bytes):
            continue
        if _RE_INICIO.match(linea):
            cerrar()
            uid, cabeceras, texto = 0, b"", b""
        m = _RE_UID.search(linea)
        if m and (uid == 0 or _RE_INICIO.match(linea)):
            uid = int(m.group(1))
        if linea.rstrip().endswith(b"}"):
            anuncio = linea[linea.rfind(b"BODY[") :]
            toca = "cabeceras" if b"HEADER" in anuncio else "texto"
    cerrar()
    return correos


def _acertados(lineas, comprobador: busqueda_exacta.Comprobador) -> set[int]:
    """UIDs de la respuesta en los que están todos los términos exactos. Trabajo de CPU."""
    aciertos: set[int] = set()
    for uid, (cabeceras, texto) in partes_de_fetch(lineas).items():
        encabezado = busqueda_exacta.cabecera_legible(cabeceras)
        cuerpo = busqueda_exacta.texto_legible(cabeceras, texto) if texto else ""
        if comprobador.esta_en(encabezado, cuerpo):
            aciertos.add(uid)
    return aciertos


async def _comprobar(
    imap,
    plan_: Plan,
    uids: list[int],
    campos: str,
    tanda: int,
    limite: float,
    comprobador: busqueda_exacta.Comprobador,
) -> tuple[set[int], int]:
    """Lee los candidatos por tandas hasta la hora límite. (aciertos, cuántos se miraron)."""
    aciertos: set[int] = set()
    mirados = 0
    for i in range(0, len(uids), tanda):
        if time.monotonic() > limite:
            break
        lote = uids[i : i + tanda]
        try:
            resp = await asyncio.wait_for(
                imap.uid("fetch", ",".join(str(u) for u in lote), campos), TOPE_TANDA_S
            )
        except asyncio.TimeoutError:
            raise _cortar(imap, plan_, f"leer {len(lote)} correos superó el tope")
        if getattr(resp, "result", "") != "OK":
            break
        # Descodificar y quitar etiquetas es CPU: fuera del bucle de eventos.
        aciertos |= await asyncio.to_thread(_acertados, resp.lines, comprobador)
        mirados += len(lote)
    return aciertos, mirados


async def ordenar(imap, uids: list[int], plan_: Plan) -> tuple[list[int], int]:
    """Los mismos UIDs con el nivel 1 delante. Devuelve (lista ordenada, cuántos son de nivel 1).

    `uids` llega ordenado por fecha y ese orden se conserva dentro de cada nivel.
    """
    t0 = time.monotonic()
    if not uids:
        return uids, 0
    recientes = uids[:MAX_ACOTADOS]
    acotado = ("UID", conjunto_de_uids(recientes)) + plan_.criterio_encabezado
    try:
        resp = await asyncio.wait_for(imap.uid_search(*acotado), TOPE_BUSQUEDA_S)
    except asyncio.TimeoutError:
        raise _cortar(imap, plan_, "la búsqueda por encabezados superó el tope")
    if getattr(resp, "result", "") != "OK":
        return uids, 0
    por_encabezado = _uids_de_busqueda(resp.lines) & set(recientes)
    mirados = 0
    if not plan_.exactos:
        nivel1 = por_encabezado
    else:
        comprobador = busqueda_exacta.Comprobador(plan_.exactos)
        limite = time.monotonic() + PRESUPUESTO_S
        candidatos = [u for u in uids if u in por_encabezado][:MAX_ENCABEZADOS]
        nivel1, _ = await _comprobar(
            imap,
            plan_,
            candidatos,
            _CAMPOS_ENCABEZADO,
            TANDA_ENCABEZADOS,
            min(limite, time.monotonic() + PRESUPUESTO_ENCABEZADOS_S),
            comprobador,
        )
        sin_comprobar = [u for u in uids if u not in nivel1][:MAX_TEXTOS]
        en_texto, mirados = await _comprobar(
            imap, plan_, sin_comprobar, _CAMPOS_TEXTO, TANDA_TEXTOS, limite, comprobador
        )
        nivel1 |= en_texto
    log.info(
        "busqueda_niveles: %d resultados, %d exactos, %d textos comprobados, %.1f s",
        len(uids),
        len(nivel1),
        mirados,
        time.monotonic() - t0,
    )
    ordenados = [u for u in uids if u in nivel1] + [u for u in uids if u not in nivel1]
    return ordenados, len(nivel1)


class Niveles:
    """Lo que el listado de UIDs necesita de los niveles. Sin plan no cambia nada."""

    def __init__(self, plan_: Plan | None = None):
        self.plan = plan_
        self.exactos: int | None = None

    @classmethod
    def preparar(
        cls,
        pedido: bool,
        consulta: str,
        buscar_en_contenido: bool,
        con_indice: bool,
        direcciones: tuple | list = (),
        clave: str = "",
    ) -> Niveles:
        if not pedido or not consulta:
            return cls()
        return cls(plan(consulta, buscar_en_contenido, con_indice, direcciones, clave))

    @property
    def prefijo(self) -> str:
        """Prefijo de la clave de caché: lo guardado con niveles tiene otro formato."""
        return PREFIJO_CACHE if self.plan else ""

    def de_cache(self, dato) -> list[int]:
        if isinstance(dato, dict):
            self.exactos = int(dato.get("exactos") or 0) if self.plan else None
            return list(dato.get("uids") or [])
        return dato

    def para_cache(self, uids: list[int]):
        if not self.plan:
            return uids
        return {"uids": uids, "exactos": self.exactos or 0}

    async def ordenar(self, imap, uids: list[int]) -> list[int]:
        if not self.plan or not uids:
            return uids
        uids, self.exactos = await ordenar(imap, uids, self.plan)
        return uids

    def informar(self, resultado: dict) -> dict:
        """Añade `exactos` (cuántos resultados son de nivel 1) cuando hubo niveles."""
        if self.plan and self.exactos is not None:
            resultado["exactos"] = self.exactos
        return resultado


def anotar(
    mensajes: list[dict], uids_pagina: list[int], desde: int, exactos: int
) -> None:
    """Pone en cada mensaje de la página si su coincidencia es «exacta» o de «contenido»."""
    posicion = {u: desde + i for i, u in enumerate(uids_pagina)}
    for m in mensajes:
        lugar = posicion.get(m.get("uid"))
        if lugar is not None:
            m["coincidencia"] = "exacta" if lugar < exactos else "contenido"
