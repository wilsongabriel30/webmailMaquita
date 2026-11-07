"""Lectura del buzón para el índice, sin modificar nada en Dovecot.

- La carpeta se abre con EXAMINE (solo lectura: no cambia \\Recent ni \\Seen) y todo se pide con
  BODY.PEEK. Una sola conexión IMAP por buzón (cuenta maestra `usuario*admin`).
- Por tanda: un FETCH de cabeceras + BODYSTRUCTURE y uno por cada número de parte de texto
  con solo el INICIO de esa parte (`<0.n>`); los adjuntos no se descargan.
"""

import re

from app.mail.clients.imap_client import _decode_lines
from app.rag import estructura, respuesta_fetch, texto

CAMPOS_CABECERA = "BODY.PEEK[HEADER.FIELDS (FROM TO CC SUBJECT DATE)]"


def citar(nombre_imap: str) -> str:
    return '"' + nombre_imap.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _numero(patron: str, texto_resp: str) -> int | None:
    m = re.search(patron, texto_resp, re.I)
    return int(m.group(1)) if m else None


async def listar(imap) -> list[dict]:
    from app.rag.carpetas import parsear_list

    resp = await imap.list('""', "*")
    if resp.result != "OK":
        return []
    return parsear_list(resp.lines)


async def examinar(imap, nombre_imap: str) -> dict | None:
    """EXAMINE -> {uidvalidity, uidnext, mensajes} o None si la carpeta no se puede abrir."""
    resp = await imap.examine(citar(nombre_imap))
    if resp.result != "OK":
        return None
    # aioimaplib solo pasa a SELECTED con SELECT; con EXAMINE hay que indicarlo para poder
    # usar UID SEARCH / UID FETCH (la carpeta queda abierta en solo lectura).
    try:
        imap.protocol.state = "SELECTED"
    except AttributeError:
        pass
    t = "\n".join(_decode_lines(resp.lines))
    return {
        "uidvalidity": _numero(r"UIDVALIDITY\s+(\d+)", t),
        "uidnext": _numero(r"UIDNEXT\s+(\d+)", t),
        "mensajes": _numero(r"(\d+)\s+EXISTS", t) or 0,
    }


async def uids(imap) -> list[int]:
    resp = await imap.uid_search("ALL", charset=None)
    if resp.result != "OK":
        raise RuntimeError("UID SEARCH falló")
    salida: list[int] = []
    for linea in _decode_lines(resp.lines):
        if "completed" in linea.lower():
            continue
        salida.extend(int(x) for x in linea.split() if x.isdigit())
    return salida


def _bytes_a_pedir(info: dict, maximo_chars: int) -> int:
    """Cuánto del inicio de la parte hace falta para obtener `maximo_chars` de texto."""
    factor = 8 if info["subtipo"] == "html" else 3
    if info["codificacion"] == "base64":
        factor = factor * 4 // 3 + 1
    return max(2048, min(32768, maximo_chars * factor))


async def leer_tanda(imap, lista_uids: list[int], maximo_chars: int) -> list[dict]:
    """-> [{uid, de, para, asunto, fecha, cuerpo}] de los UID pedidos (los que existan)."""
    if not lista_uids:
        return []
    conjunto = ",".join(str(u) for u in lista_uids)
    resp = await imap.uid("fetch", conjunto, f"(UID BODYSTRUCTURE {CAMPOS_CABECERA})")
    if resp.result != "OK":
        raise RuntimeError("UID FETCH de cabeceras falló")
    leidos: dict[int, dict] = {}
    for d in respuesta_fetch.mensajes(resp.lines):
        try:
            uid = int(d.get("UID") or 0)
        except (TypeError, ValueError):
            continue
        if uid <= 0:
            continue
        info = estructura.parte_de_texto(d.get("BODYSTRUCTURE"))
        leidos[uid] = {
            "uid": uid,
            **texto.cabeceras(respuesta_fetch.cabeceras(d) or b""),
            "cuerpo": "",
            "_info": info,
        }
    if maximo_chars > 0:
        grupos: dict[tuple, list[int]] = {}
        for uid, m in leidos.items():
            info = m["_info"]
            if info:
                clave = (info["parte"], _bytes_a_pedir(info, maximo_chars))
                grupos.setdefault(clave, []).append(uid)
        for (parte, n), grupo in grupos.items():
            r = await imap.uid(
                "fetch", ",".join(map(str, grupo)), f"(UID BODY.PEEK[{parte}]<0.{n}>)"
            )
            if r.result != "OK":
                continue  # sin cuerpo: se indexa igual con las cabeceras
            for d in respuesta_fetch.mensajes(r.lines):
                try:
                    uid = int(d.get("UID") or 0)
                except (TypeError, ValueError):
                    continue
                if uid in leidos:
                    datos = respuesta_fetch.parte_de_cuerpo(d)
                    if isinstance(datos, str):
                        datos = datos.encode("utf-8", "replace")
                    leidos[uid]["cuerpo"] = texto.cuerpo(
                        datos, leidos[uid]["_info"], maximo_chars
                    )
    salida = []
    for uid in lista_uids:
        m = leidos.get(uid)
        if m:
            m.pop("_info", None)
            salida.append(m)
    return salida
