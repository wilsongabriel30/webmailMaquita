"""
Adjuntos de cada correo del listado (clip y nombres en la fila, como Outlook; 07/11/2026).

Una sola orden `UID FETCH ... (UID BODYSTRUCTURE)` para toda la página. Si falla o tarda más de
`TIEMPO_MAX_S`, la lista sale sin clips (fallo blando) y la conexión se marca como sucia para que
el pool la cierre en vez de reutilizarla con un comando a medias.

Revisión del 07/11/2026 (tarde):
- nombres con paréntesis («informe (final).pdf»), con tildes/ñ (literales IMAP `{N}`) y RFC 2231;
- solo cuenta la disposición ATTACHMENT de verdad, no la palabra dentro de un nombre («Attachment-1.jpeg»);
- caché en Redis por (usuario, carpeta, uid): el BODYSTRUCTURE de un correo no cambia nunca.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import urllib.parse

from .busqueda_adjuntos import _decodificar

log = logging.getLogger(__name__)

TIEMPO_MAX_S = 3.0
MAX_NOMBRES = 3
VIDA_CACHE_S = 2 * 24 * 3600

_RE_UID = re.compile(r"\b(\d+) FETCH \(UID (\d+)\b")
# ("ATTACHMENT" NIL) o ("ATTACHMENT" ("FILENAME" "x (y).pdf" ...)): las cadenas pueden traer paréntesis.
_RE_ADJUNTO = re.compile(
    r'\("ATTACHMENT"\s+(NIL|\((?:"(?:[^"\\]|\\.)*"|[^()"])*\))\)', re.I
)
_RE_FILENAME = re.compile(r'"(?:FILENAME|NAME)\*?"\s+"((?:[^"\\]|\\.)*)"', re.I)
_RE_LITERAL = re.compile(r"\{(\d+)\}\s*$")
_RE_2231 = re.compile(r"^([\w-]+)'[^']*'(.*)$")


def _desescapar(valor: str) -> str:
    return valor.replace('\\"', '"').replace("\\\\", "\\")


def _nombre(valor: str) -> str:
    """Nombre legible: RFC 2231 (`utf-8''Factura%20n%C2%BA1.pdf`) o =?utf-8?B?...?=."""
    valor = _desescapar(valor)
    m = _RE_2231.match(valor)
    if m:
        try:
            return urllib.parse.unquote(
                m.group(2), encoding=m.group(1) or "utf-8", errors="replace"
            )
        except LookupError:
            return urllib.parse.unquote(m.group(2), errors="replace")
    return _decodificar(valor)


def adjuntos_de_estructura(estructura: str) -> tuple[bool, list[str]]:
    """(hay adjuntos, nombres) a partir del BODYSTRUCTURE. Las partes INLINE no cuentan."""
    nombres: list[str] = []
    hay = False
    for m in _RE_ADJUNTO.finditer(estructura):
        hay = True
        f = _RE_FILENAME.search(m.group(1))
        if f:
            n = _nombre(f.group(1)).strip()
            if n and n not in nombres:
                nombres.append(n)
        if len(nombres) >= MAX_NOMBRES:
            break
    return hay, nombres


def _texto_respuesta(lines) -> str:
    """Une las líneas de aioimaplib. Un literal `{N}` (nombres con 8 bits) llega como elemento
    aparte: se vuelve a poner como cadena entre comillas para que las expresiones lo lean.
    """
    partes: list[str] = []
    literal_pendiente = False
    for linea in lines:
        s = (
            linea.decode("utf-8", "replace")
            if isinstance(linea, (bytes, bytearray))
            else str(linea)
        )
        if literal_pendiente:
            partes.append('"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"')
            literal_pendiente = False
            continue
        m = _RE_LITERAL.search(s)
        if m:
            partes.append(s[: m.start()])
            literal_pendiente = True
        else:
            partes.append(s + "\n")
    return "".join(partes)


def _clave(username: str, folder: str, uid: int) -> str:
    return f"adj:{username}:{folder}:{uid}"


async def _leer_cache(
    redis, username: str, folder: str, uids: list[int]
) -> dict[int, tuple[bool, list[str]]]:
    if redis is None or not username:
        return {}
    try:
        valores = await redis.mget([_clave(username, folder, u) for u in uids])
    except Exception as e:  # noqa: BLE001 - la caché es de cortesía
        log.debug("adjuntos: caché ilegible (%s)", type(e).__name__)
        return {}
    resultado: dict[int, tuple[bool, list[str]]] = {}
    for u, v in zip(uids, valores):
        if not v:
            continue
        try:
            hay, nombres = json.loads(v)
            resultado[u] = (bool(hay), [str(n) for n in nombres])
        except Exception:  # noqa: BLE001
            continue
    return resultado


async def _guardar_cache(
    redis, username: str, folder: str, datos: dict[int, tuple[bool, list[str]]]
) -> None:
    if redis is None or not username or not datos:
        return
    try:
        pipe = redis.pipeline()
        for u, (hay, nombres) in datos.items():
            pipe.set(
                _clave(username, folder, u), json.dumps([hay, nombres]), ex=VIDA_CACHE_S
            )
        await pipe.execute()
    except Exception as e:  # noqa: BLE001
        log.debug("adjuntos: no se pudo guardar la caché (%s)", type(e).__name__)


async def adjuntos_por_uid(
    imap, uids: list[int], redis=None, username: str = "", folder: str = ""
) -> dict[int, tuple[bool, list[str]]]:
    """{uid: (hay adjuntos, nombres)} para los UIDs dados. Ante cualquier problema devuelve lo que haya."""
    if not uids:
        return {}
    uids = [int(u) for u in uids]
    resultado = await _leer_cache(redis, username, folder, uids)
    faltan = [u for u in uids if u not in resultado]
    if not faltan:
        return resultado
    conjunto = ",".join(str(u) for u in faltan)
    try:
        resp = await asyncio.wait_for(
            imap.uid("fetch", conjunto, "(UID BODYSTRUCTURE)"), TIEMPO_MAX_S
        )
    except asyncio.TimeoutError:
        # La orden sigue en curso en Dovecot: esta conexión no debe volver al pool.
        setattr(imap, "conexion_sucia", True)
        log.warning(
            "adjuntos: BODYSTRUCTURE de %d correos superó %.0f s; lista sin clips",
            len(faltan),
            TIEMPO_MAX_S,
        )
        return resultado
    except Exception as e:  # noqa: BLE001
        log.info("adjuntos: sin estructura (%s: %s)", type(e).__name__, e)
        return resultado
    if getattr(resp, "result", "OK") != "OK":
        return resultado
    texto = _texto_respuesta(getattr(resp, "lines", []) or [])
    trozos = _RE_UID.split(texto)
    nuevos: dict[int, tuple[bool, list[str]]] = {}
    # split deja: [antes, seq, uid, resto, seq, uid, resto, ...]
    for i in range(1, len(trozos) - 2, 3):
        try:
            uid = int(trozos[i + 1])
        except ValueError:
            continue
        nuevos[uid] = adjuntos_de_estructura(trozos[i + 2])
    # Los pedidos que no vinieron en la respuesta quedan como «sin adjuntos» (no se cachean).
    resultado.update(nuevos)
    await _guardar_cache(redis, username, folder, nuevos)
    return resultado
