"""Del inicio de la parte de texto (bytes crudos) al contenido que se indexa.

El contenido de cada correo queda así (FORMATO 2, 04/11/2026):
    Carpeta: Enviados | Fecha: 2026-10-13 | De: ... | Para: ... | Asunto: ... | <cuerpo>
El cuerpo es el comienzo del texto, sin citas del correo anterior («> ...», «El ... escribió:»),
hasta RAG_CUERPO_CHARS caracteres. Se quitan los caracteres NUL: PostgreSQL no los admite en
`text` y uno solo abortaba toda la indexación nocturna (04/11/2026 09:17).
"""

import base64
import binascii
import codecs
import email
import email.policy
import email.utils
import html
import quopri
import re

FORMATO = 2  # sube si cambia el contenido indexado: los correos del formato anterior se rehacen

_RE_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_RE_BLOQUES_HTML = re.compile(r"<(script|style|head|title)\b.*?</\1\s*>", re.I | re.S)
_RE_SALTOS_HTML = re.compile(r"<\s*(br|/p|/div|/tr|/li|/h\d)\b[^>]*>", re.I)
_RE_ETIQUETA = re.compile(r"<[^>]*>", re.S)
_RE_CORTE_CITA = re.compile(
    r"^\s*(-{2,}\s*(original message|mensaje original|forwarded message|mensaje reenviado)"
    r"|_{10,}"
    r"|(el|on)\s.{4,200}\s(escribi[oó]|wrote)\s*:)",
    re.I | re.M,
)


def sin_nul(s) -> str:
    """Texto apto para PostgreSQL: sin NUL ni caracteres de control (salvo \\t \\n \\r)."""
    if s is None:
        return ""
    return _RE_CONTROL.sub(" ", str(s))


def decodificar(datos: bytes, codificacion: str = "", charset: str = "") -> str:
    """Bytes de una parte MIME (posiblemente cortados a mitad) -> texto."""
    datos = bytes(datos or b"")
    cod = (codificacion or "").lower()
    if cod == "base64":
        limpio = re.sub(rb"[^A-Za-z0-9+/=]", b"", datos)
        limpio = limpio[: len(limpio) - len(limpio) % 4]
        try:
            datos = base64.b64decode(limpio)
        except (binascii.Error, ValueError):
            datos = b""
    elif cod == "quoted-printable":
        datos = re.sub(
            rb"=[0-9A-Fa-f]?$", b"", datos
        )  # secuencia «=X» cortada al final
        datos = quopri.decodestring(datos)
    nombre = (charset or "utf-8").strip().strip('"').lower() or "utf-8"
    try:
        codecs.lookup(nombre)
    except LookupError:
        nombre = "utf-8"
    texto = datos.decode(nombre, "replace")
    if nombre == "utf-8" and texto.count("�") > max(3, len(texto) // 50):
        texto = datos.decode(
            "latin-1", "replace"
        )  # correos antiguos sin charset declarado
    return texto.rstrip(
        "\ufffd"
    )  # carácter multibyte cortado al final del trozo pedido


def html_a_texto(s: str) -> str:
    s = _RE_BLOQUES_HTML.sub(" ", s)
    s = _RE_SALTOS_HTML.sub("\n", s)
    s = _RE_ETIQUETA.sub(" ", s)
    return html.unescape(s)


def limpiar_cuerpo(texto: str, maximo: int) -> str:
    """Quita citas y espacios repetidos y recorta a `maximo` caracteres."""
    if not texto or maximo <= 0:
        return ""
    m = _RE_CORTE_CITA.search(texto)
    if m and m.start() > 0:
        texto = texto[: m.start()]
    lineas = [ln for ln in texto.splitlines() if not ln.lstrip().startswith(">")]
    plano = re.sub(r"\s+", " ", sin_nul(" ".join(lineas))).strip()
    return plano[:maximo]


def cuerpo(datos, info: dict | None, maximo: int) -> str:
    if not datos or not info:
        return ""
    t = decodificar(datos, info.get("codificacion", ""), info.get("charset", ""))
    if info.get("subtipo") == "html":
        t = html_a_texto(t)
    return limpiar_cuerpo(t, maximo)


def _cabecera(msg, nombre: str) -> str:
    try:
        return str(msg.get(nombre, "") or "")
    except Exception:  # cabecera mal formada: se devuelve tal cual
        try:
            return str(msg.get_all(nombre, [""])[0])
        except Exception:
            return ""


def cabeceras(crudo) -> dict:
    """Cabeceras (bytes) -> {de, para, asunto, fecha} decodificadas (RFC 2047)."""
    if isinstance(crudo, str):
        crudo = crudo.encode("utf-8", "replace")
    try:
        msg = email.message_from_bytes(bytes(crudo or b""), policy=email.policy.default)
    except Exception:
        return {"de": "", "para": "", "asunto": "", "fecha": ""}
    fecha = ""
    bruto = _cabecera(msg, "Date")
    if bruto:
        try:
            fecha = email.utils.parsedate_to_datetime(bruto).date().isoformat()
        except Exception:
            fecha = ""
    para = _cabecera(msg, "To")
    cc = _cabecera(msg, "Cc")
    if cc:
        para = f"{para}, {cc}" if para else cc
    return {
        "de": sin_nul(_cabecera(msg, "From")).strip()[:300],
        "para": sin_nul(para).strip()[:300],
        "asunto": sin_nul(_cabecera(msg, "Subject")).strip()[:500],
        "fecha": fecha,
    }


def contenido(etiqueta_carpeta: str, cab: dict, texto_cuerpo: str) -> str:
    partes = [f"Carpeta: {etiqueta_carpeta}"]
    if cab.get("fecha"):
        partes.append(f"Fecha: {cab['fecha']}")
    partes.append(f"De: {cab.get('de', '')}")
    if cab.get("para"):
        partes.append(f"Para: {cab['para']}")
    partes.append(f"Asunto: {cab.get('asunto', '')}")
    if texto_cuerpo:
        partes.append(texto_cuerpo)
    return sin_nul(" | ".join(partes))
