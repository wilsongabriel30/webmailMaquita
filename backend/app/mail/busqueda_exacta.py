"""Comprobar que un valor o una frase están DE VERDAD en un correo.

El índice de texto de Dovecot no sabe de frases ni de valores (comprobado el 13/11/2026 en un
buzón de 209 847 mensajes): parte lo escrito por sus signos y busca cada trozo por su comienzo.
«205,6» es para él «205» Y «6…» —1 404 correos, casi ninguno con ese valor— y «informe mensual»
entre comillas trae lo mismo que las dos palabras sueltas.

El índice sigue sirviendo para lo que es bueno: dar candidatos en milésimas. Aquí está la segunda
mitad: mirar el asunto y el principio del texto de un candidato y decir si el valor o la frase
aparecen tal cual. Módulo puro (sin IMAP ni red) para poder probarlo entero.

- Valores: la coma y el punto valen lo mismo («205,6» = «205.6», «1.250,00» = «1,250.00») y los
  ceros de más a la derecha no cuentan («205,6» = «205,60»). No vale como acierto un número más
  largo que lo contenga: ni «1.205,6», ni «205,65», ni «3205,6».
- Frases: sin mayúsculas ni tildes, y con cualquier signo o salto de línea entre las palabras.
"""

from __future__ import annotations

import base64
import binascii
import email
import html
import quopri
import re
import unicodedata
from email.header import decode_header, make_header

_VALOR = re.compile(r"[$€]?(\d+(?:[.,]\d+)+)%?")
_NO_ALFANUMERICO = re.compile(r"[^0-9a-z]+")
_ESTILOS = re.compile(r"<(style|script|head)\b.*?(?:</\1\s*>|\Z)", re.S | re.I)
_ETIQUETAS = re.compile(r"<[^>]{0,2000}>")
_ESPACIOS = re.compile(r"\s+")
# Los ceros de más solo se toleran tras uno o dos decimales («205,6» → «205,60»): con tres
# cifras al final lo escrito puede ser un millar («1.250») y «1.2500» sería otro número.
_MAX_DECIMALES_CON_CEROS = 2


def valor_numerico(termino: str) -> str | None:
    """«205,6», «$1.250,00» o «12,5%» → el valor con puntos («205.6»). `None` si no es un valor."""
    m = _VALOR.fullmatch((termino or "").strip())
    return m.group(1).replace(",", ".") if m else None


def es_exacto(termino: str) -> bool:
    """¿El término hay que comprobarlo en el correo? Valores con decimales o miles, y frases."""
    return valor_numerico(termino) is not None or " " in termino.strip()


def plano(texto: str) -> str:
    """Minúsculas, sin tildes ni eñes, y todo signo convertido en un espacio."""
    t = unicodedata.normalize("NFD", (texto or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return _NO_ALFANUMERICO.sub(" ", t).strip()


def _patron_valor(valor: str) -> re.Pattern[str]:
    grupos = valor.split(".")
    ceros = "0*" if len(grupos[-1]) <= _MAX_DECIMALES_CON_CEROS else ""
    return re.compile(
        r"(?<!\d)(?<!\d[.,])" + "[.,]".join(grupos) + ceros + r"(?!\d)(?![.,]\d)"
    )


class Comprobador:
    """Los términos exactos de una búsqueda, listos para comprobarlos en muchos correos."""

    def __init__(self, terminos: list[str] | tuple[str, ...]):
        self._valores: list[re.Pattern[str]] = []
        self._frases: list[re.Pattern[str]] = []
        for t in terminos:
            valor = valor_numerico(t)
            if valor is not None:
                self._valores.append(_patron_valor(valor))
            elif plano(t):
                # La frase empieza en comienzo de palabra; la última palabra puede seguir
                # («informe mensual» acierta en «informe mensualizado»), como hace el índice.
                self._frases.append(re.compile(r"(?<![0-9a-z])" + re.escape(plano(t))))

    def __bool__(self) -> bool:
        return bool(self._valores or self._frases)

    def esta_en(self, *textos: str) -> bool:
        """True si TODOS los términos exactos aparecen en alguno de los textos."""
        junto = "\n".join(t for t in textos if t)
        if not junto:
            return False
        if not all(p.search(junto) for p in self._valores):
            return False
        if not self._frases:
            return True
        llano = plano(junto)
        return all(p.search(llano) for p in self._frases)


def cabecera_legible(cruda: bytes | str) -> str:
    """Las cabeceras pedidas (asunto, remitente…) ya descodificadas y en una sola línea cada una."""
    if isinstance(cruda, (bytes, bytearray)):
        cruda = bytes(cruda).decode("utf-8", "replace")
    desplegada = re.sub(r"\r?\n[ \t]+", " ", cruda)
    try:
        return str(make_header(decode_header(desplegada)))
    except Exception:  # una cabecera mal formada no impide comprobar el resto
        return desplegada


def _a_texto(datos: bytes, juego: str | None) -> str:
    for candidato in (juego, "utf-8", "latin-1"):
        if not candidato:
            continue
        try:
            return datos.decode(candidato)
        except (LookupError, UnicodeDecodeError):
            continue
    return datos.decode("utf-8", "replace")


def _contenido(parte) -> bytes:
    """El contenido de una parte ya descodificado, aunque el base64 venga cortado a la mitad."""
    crudo = parte.get_payload()
    if not isinstance(crudo, str):
        return b""
    datos = crudo.encode("utf-8", "surrogateescape")
    codificacion = str(parte.get("Content-Transfer-Encoding") or "").strip().lower()
    try:
        if codificacion == "base64":
            junto = b"".join(datos.split())
            return base64.b64decode(junto[: len(junto) - len(junto) % 4])
        if codificacion == "quoted-printable":
            return quopri.decodestring(datos)
    except (binascii.Error, ValueError):
        pass
    return datos


def _sin_etiquetas(pagina: str) -> str:
    return html.unescape(_ETIQUETAS.sub(" ", _ESTILOS.sub(" ", pagina)))


def texto_legible(cabeceras: bytes, cuerpo: bytes) -> str:
    """El texto que una persona leería en el principio de un correo.

    `cabeceras` debe traer Content-Type y Content-Transfer-Encoding; `cuerpo` es el comienzo del
    cuerpo (puede venir cortado a la mitad de una parte: se aprovecha lo que haya). Descodifica
    base64 y quoted-printable y quita las etiquetas del HTML. No abre adjuntos.
    """
    crudo = bytes(cabeceras).rstrip(b"\r\n") + b"\r\n\r\n" + bytes(cuerpo)
    try:
        mensaje = email.message_from_bytes(crudo)
    except Exception:
        return _a_texto(bytes(cuerpo), None)
    trozos: list[str] = []
    for parte in mensaje.walk():
        if parte.get_content_maintype() != "text" or parte.get_filename():
            continue
        datos = _contenido(parte)
        if not datos:
            continue
        texto = _a_texto(datos, parte.get_content_charset())
        if parte.get_content_subtype() == "html":
            texto = _sin_etiquetas(texto)
        trozos.append(texto)
    return _ESPACIOS.sub(" ", " ".join(trozos).replace("\xa0", " ")).strip()
