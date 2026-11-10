"""Aplicar una regla de correo a los correos que YA están en una carpeta (10/11/2026).

Las reglas Sieve solo actúan sobre el correo que llega. Quien crea una regla suele querer que
también ordene lo anterior («todo lo de dirección a la carpeta de María Jesús»). Aquí se busca en
la carpeta por IMAP qué correos cumplen la regla y se les aplican sus acciones.

Cómo se decide si un correo cumple cada condición:

- Lo que IMAP SEARCH resuelve igual que Sieve (cuerpo, tamaño, encabezado presente) se le deja
  a IMAP.
- Para De/Para/Cc/Asunto/Encabezado se usa IMAP SEARCH solo para ACOTAR candidatos («contiene»)
  y la decisión final se toma aquí con las mismas reglas que Sieve: direcciones comparadas por
  la dirección (no por el nombre), «es exactamente», patrón con * y ?, expresión regular, y las
  negaciones. Cuando no se puede acotar (negaciones, regex) se revisan los últimos `TOPE`
  correos de la carpeta y se informa `parcial = True` si había más.

Acciones: mover, copiar, marcar, leído y «eliminar» (a la Papelera, nunca se borra en firme al
aplicar hacia atrás). Reenviar no se aplica a correos anteriores: se informa en `omitidas`.
"""

from __future__ import annotations

import email
import email.header
import email.utils
import fnmatch
import logging
import re
from dataclasses import dataclass, field
from typing import Iterable, Optional

from app.mail.clients.imap_acciones import mover_uids_con_mapa
from app.mail.clients.imap_client import _quote_folder
from app.sieve.generador import _operador_base
from app.sieve.modelos import FilterCondition, FilterRule

logger = logging.getLogger("sieve.aplicar")

TOPE = 5000  # correos revisados cuando no se puede acotar por IMAP
LOTE_FETCH = 300
LOTE_ACCION = 500
CARPETA_PAPELERA = "Trash"

_CAMPOS_DIRECCION = {
    "from": ["from"],
    "to": ["to"],
    "cc": ["cc"],
    "recipients": ["to", "cc"],
}
_RE_FETCH = re.compile(r"^\d+\s+FETCH\s+\(", re.I)
_RE_UID = re.compile(r"\bUID\s+(\d+)")
_RE_SIZE = re.compile(r"RFC822\.SIZE\s+(\d+)")


@dataclass
class Cabecera:
    """Lo que hace falta de un correo para evaluar las condiciones."""

    uid: int
    size: int = 0
    direcciones: dict[str, list[str]] = field(
        default_factory=dict
    )  # from/to/cc -> direcciones
    asunto: str = ""
    encabezados: dict[str, list[str]] = field(
        default_factory=dict
    )  # nombre en minúsculas


@dataclass
class Resultado:
    folder: str
    revisados: int = 0
    coinciden: int = 0
    parcial: bool = False
    movidos: int = 0
    copiados: int = 0
    marcados: int = 0
    leidos: int = 0
    papelera: int = 0
    destino: Optional[str] = None
    omitidas: list[str] = field(default_factory=list)

    def como_dict(self) -> dict:
        return self.__dict__.copy()


# ---------------------------------------------------------------------------
# Condiciones → IMAP SEARCH
# ---------------------------------------------------------------------------


def _cadena_imap(valor: str) -> Optional[str]:
    """`valor` entre comillas para IMAP SEARCH, o None si no se puede mandar así (no ASCII, comillas)."""
    if (
        not valor
        or any(c in valor for c in '"\\\r\n')
        or not valor.isascii()
        or not valor.isprintable()
    ):
        return None
    return f'"{valor}"'


def _nombre_encabezado(cond: FilterCondition) -> str:
    if cond.field == "list":
        return "List-Id"
    return (cond.header or "").strip()


def criterio_imap(cond: FilterCondition) -> tuple[Optional[str], bool]:
    """(criterio IMAP SEARCH o None, decide_solo).

    `decide_solo` = True cuando IMAP responde exactamente lo que Sieve haría y no hace falta
    comprobar aquí (cuerpo, tamaño, encabezado presente). Con False el criterio solo ACOTA y
    la decisión se toma con `cumple`. None = no se puede acotar: revisar los últimos TOPE.
    """
    negado, base = _operador_base(cond.operator)
    campo = cond.field
    if campo == "size":
        try:
            octetos = int(cond.value.strip()) * 1024
        except ValueError:
            return None, False
        return (f"SMALLER {octetos}" if base == "under" else f"LARGER {octetos}"), True
    if base == "exists":
        nombre = _nombre_encabezado(cond)
        if campo in _CAMPOS_DIRECCION:
            nombre = campo if campo != "recipients" else ""
        if campo == "subject":
            nombre = "Subject"
        if not nombre:
            return None, False
        crit = f'HEADER {nombre} ""'
        return (f"NOT {crit}" if negado else crit), True
    if campo == "body":
        if base != "contains":
            return None, False  # regex de cuerpo: sin acotación posible
        cadena = _cadena_imap(cond.value)
        if cadena is None:
            return None, False
        return (f"NOT BODY {cadena}" if negado else f"BODY {cadena}"), True
    if negado or base in ("regex",):
        return None, False
    # contains / is / matches sobre direcciones, asunto o encabezado: acotar por «contiene»
    literal = cond.value
    if base == "matches":
        trozos = [t for t in re.split(r"[*?]", cond.value) if len(t) >= 3]
        if not trozos:
            return None, False
        literal = max(trozos, key=len)
    cadena = _cadena_imap(literal)
    if cadena is None:
        return None, False
    if campo in ("from", "to", "cc"):
        return f"{campo.upper()} {cadena}", False
    if campo == "recipients":
        return f"OR TO {cadena} CC {cadena}", False
    if campo == "subject":
        return f"SUBJECT {cadena}", False
    nombre = _nombre_encabezado(cond)
    if not nombre or not re.fullmatch(r"[A-Za-z0-9-]+", nombre):
        return None, False
    return f"HEADER {nombre} {cadena}", False


# ---------------------------------------------------------------------------
# Evaluación local con la semántica de Sieve
# ---------------------------------------------------------------------------


def _valores(cond: FilterCondition, cab: Cabecera) -> list[str]:
    """Textos contra los que se compara. Como en el Sieve generado, «es exactamente» y «coincide con el
    patrón» miran solo la dirección en De/Para/Cc; «contiene» y la expresión regular, el encabezado
    entero («Nombre <dirección>»)."""
    campo = cond.field
    _negado, base = _operador_base(cond.operator)
    if campo in _CAMPOS_DIRECCION:
        out: list[str] = []
        for c in _CAMPOS_DIRECCION[campo]:
            if base in ("is", "matches"):
                out.extend(cab.direcciones.get(c, []))
            else:
                out.extend(cab.encabezados.get(c, []))
        return out
    if campo == "subject":
        return [cab.asunto]
    if campo == "body":
        return []
    nombre = _nombre_encabezado(cond).lower()
    return cab.encabezados.get(nombre, []) if nombre else []


def _compara(base: str, valor: str, texto: str) -> bool:
    v, t = valor.lower(), texto.lower()
    if base == "contains":
        return v in t
    if base == "is":
        return v == t
    if base == "matches":
        patron = v.replace("[", "[[]")
        return fnmatch.fnmatchcase(t, patron)
    if base == "regex":
        try:
            return re.search(valor, texto, re.I) is not None
        except re.error:
            return False
    return False


def cumple(cond: FilterCondition, cab: Cabecera) -> bool:
    """¿El correo cumple la condición? (misma semántica que el Sieve generado)."""
    negado, base = _operador_base(cond.operator)
    if cond.field == "size":
        try:
            kb = int(cond.value.strip())
        except ValueError:
            return False
        return cab.size > kb * 1024 if base == "over" else cab.size < kb * 1024
    valores = _valores(cond, cab)
    if base == "exists":
        hay = bool(valores)
        return (not hay) if negado else hay
    hay = any(_compara(base, cond.value, t) for t in valores)
    return (not hay) if negado else hay


# ---------------------------------------------------------------------------
# IMAP: buscar, leer encabezados
# ---------------------------------------------------------------------------


def _uids_de_busqueda(lines: Iterable) -> list[int]:
    uids: list[int] = []
    for line in lines:
        if isinstance(line, (bytes, bytearray)):
            line = line.decode("utf-8", errors="replace")
        line = str(line).strip()
        if (
            not line
            or line.lower().endswith("completed.")
            or "completed (" in line.lower()
        ):
            continue
        for tok in line.split():
            if tok.isdigit():
                uids.append(int(tok))
    return uids


async def _buscar(imap, criterio: str) -> list[int]:
    resp = await imap.uid_search(criterio)
    if resp.result != "OK":
        logger.warning("UID SEARCH %s falló: %s", criterio[:80], resp.result)
        return []
    return _uids_de_busqueda(resp.lines)


def _decodificar(texto: str) -> str:
    try:
        return str(email.header.make_header(email.header.decode_header(texto)))
    except Exception:
        return texto


def parsear_cabecera(uid: int, size: int, crudo: str) -> Cabecera:
    """Construye la Cabecera a partir del bloque de encabezados (HEADER.FIELDS)."""
    msg = email.message_from_string(crudo)
    cab = Cabecera(uid=uid, size=size)
    for campo in ("from", "to", "cc"):
        pares = email.utils.getaddresses(
            [_decodificar(v) for v in msg.get_all(campo, [])]
        )
        cab.direcciones[campo] = [d.strip() for _n, d in pares if d.strip()]
    cab.asunto = " ".join(_decodificar(msg.get("subject", "")).split())
    for nombre, valor in msg.items():
        cab.encabezados.setdefault(nombre.lower(), []).append(
            " ".join(_decodificar(valor).split())
        )
    return cab


def parsear_fetch(lines: Iterable) -> list[tuple[int, int, str]]:
    """[(uid, tamaño, encabezados crudos)] de una respuesta UID FETCH con HEADER.FIELDS."""
    textos: list[str] = []
    for line in lines:
        if isinstance(line, (bytes, bytearray)):
            textos.append(line.decode("utf-8", errors="replace"))
        else:
            textos.append(str(line))
    out: list[tuple[int, int, str]] = []
    i = 0
    while i < len(textos):
        linea = textos[i]
        if _RE_FETCH.match(linea):
            m_uid = _RE_UID.search(linea)
            m_size = _RE_SIZE.search(linea)
            uid = int(m_uid.group(1)) if m_uid else 0
            size = int(m_size.group(1)) if m_size else 0
            crudo = ""
            j = i + 1
            while j < len(textos) and not _RE_FETCH.match(textos[j]):
                t = textos[j]
                if (
                    t.strip() != ")"
                    and "completed" not in t.lower()
                    and not re.match(r"\s*BODY\[", t)
                    and not crudo
                ):
                    crudo = t
                j += 1
            if uid:
                out.append((uid, size, crudo))
            i = j
        else:
            i += 1
    return out


async def _leer_cabeceras(imap, uids: list[int], extra: list[str]) -> list[Cabecera]:
    campos = ["FROM", "TO", "CC", "SUBJECT", "LIST-ID"] + [
        e.upper() for e in extra if e
    ]
    items = f"(UID RFC822.SIZE BODY.PEEK[HEADER.FIELDS ({' '.join(dict.fromkeys(campos))})])"
    out: list[Cabecera] = []
    for k in range(0, len(uids), LOTE_FETCH):
        lote = uids[k : k + LOTE_FETCH]
        resp = await imap.uid("fetch", ",".join(str(u) for u in lote), items)
        if resp.result != "OK":
            continue
        for uid, size, crudo in parsear_fetch(resp.lines):
            out.append(parsear_cabecera(uid, size, crudo))
    return out


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------


async def uids_que_cumplen(imap, regla: FilterRule, resultado: Resultado) -> list[int]:
    """UIDs de la carpeta (ya seleccionada) que cumplen la regla."""
    conjuntos: list[set[int]] = []
    todos: Optional[list[int]] = None
    extra = [c.header or "" for c in regla.conditions if c.field == "header"]
    for cond in regla.conditions:
        criterio, decide_solo = criterio_imap(cond)
        if criterio is not None and decide_solo:
            conjuntos.append(set(await _buscar(imap, criterio)))
            continue
        if criterio is not None:
            candidatos = await _buscar(imap, criterio)
        else:
            if cond.field == "body":
                resultado.omitidas.append(
                    "condición sobre el cuerpo con expresión regular"
                )
                conjuntos.append(set())
                continue
            if todos is None:
                todos = await _buscar(imap, "ALL")
                if len(todos) > TOPE:
                    resultado.parcial = True
                    todos = todos[-TOPE:]
            candidatos = todos
        cabeceras = await _leer_cabeceras(imap, candidatos, extra)
        resultado.revisados = max(resultado.revisados, len(cabeceras))
        conjuntos.append({c.uid for c in cabeceras if cumple(cond, c)})
    if not conjuntos:
        return []
    if regla.match == "anyof":
        union: set[int] = set()
        for s in conjuntos:
            union |= s
        return sorted(union)
    inter = set(conjuntos[0])
    for s in conjuntos[1:]:
        inter &= s
    return sorted(inter)


def _lotes(uids: list[int]) -> Iterable[str]:
    for k in range(0, len(uids), LOTE_ACCION):
        yield ",".join(str(u) for u in uids[k : k + LOTE_ACCION])


async def _asegurar_carpeta(imap, carpeta: str) -> None:
    try:
        await imap.create(_quote_folder(carpeta))
    except Exception:
        pass


async def aplicar_regla_existentes(
    imap, regla: FilterRule, carpeta: str = "INBOX"
) -> dict:
    """Aplica la regla a los correos que ya están en `carpeta`. Devuelve el recuento."""
    resultado = Resultado(folder=carpeta)
    resp = await imap.select(_quote_folder(carpeta))
    if resp.result != "OK":
        raise ValueError(f"No se pudo abrir la carpeta {carpeta}")
    uids = await uids_que_cumplen(imap, regla, resultado)
    resultado.coinciden = len(uids)
    if not uids:
        return resultado.como_dict()

    # Primero lo que no cambia de sitio; mover/eliminar al final (cambian los UID).
    mueven: list = []
    for accion in regla.actions:
        if accion.type in ("move", "delete"):
            mueven.append(accion)
        elif accion.type == "copy" and accion.value:
            await _asegurar_carpeta(imap, accion.value)
            for lote in _lotes(uids):
                r = await imap.uid("copy", lote, _quote_folder(accion.value))
                if r.result == "OK":
                    resultado.copiados += lote.count(",") + 1
        elif accion.type == "flag":
            for lote in _lotes(uids):
                await imap.uid("store", lote, "+FLAGS", "(\\Flagged)")
            resultado.marcados = len(uids)
        elif accion.type == "read":
            for lote in _lotes(uids):
                await imap.uid("store", lote, "+FLAGS", "(\\Seen)")
            resultado.leidos = len(uids)
        elif accion.type in ("forward", "forward_copy"):
            resultado.omitidas.append(f"reenviar a {accion.value or ''}".strip())

    # Solo un movimiento efectivo: el primero (los demás ya no encontrarían el correo).
    for accion in mueven[:1]:
        destino = accion.value if accion.type == "move" else CARPETA_PAPELERA
        if not destino or destino == carpeta:
            continue
        await _asegurar_carpeta(imap, destino)
        for lote in _lotes(uids):
            ok, _mapa = await mover_uids_con_mapa(imap, lote, _quote_folder(destino))
            if ok:
                n = lote.count(",") + 1
                if accion.type == "move":
                    resultado.movidos += n
                else:
                    resultado.papelera += n
        resultado.destino = destino
    for accion in mueven[1:]:
        resultado.omitidas.append("segunda acción de mover (ya movido)")
    return resultado.como_dict()
