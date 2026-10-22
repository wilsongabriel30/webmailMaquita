"""Texto de formatos que ya son texto por dentro: HTML, RTF y texto plano.

Sin programas externos: HTML con html.parser (sin ejecutar nada, sin descargar nada) y RTF con un
lector propio que solo saca el texto y salta imágenes, objetos incrustados y tablas de estilos.
"""

import re
from html.parser import HTMLParser


def a_texto(datos: bytes) -> str:
    """Bytes a texto: UTF-8 si lo es; si no, Windows-1252 (lo habitual en adjuntos antiguos)."""
    try:
        return datos.decode("utf-8")
    except UnicodeDecodeError:
        return datos.decode("cp1252", errors="replace")


class _Html(HTMLParser):
    _IGNORAR = frozenset({"script", "style", "noscript", "template", "svg"})
    _BLOQUE = frozenset({"p", "div", "br", "li", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6", "title"})

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []
        self._dentro = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._IGNORAR:
            self._dentro += 1
        if tag in self._BLOQUE:
            self.partes.append("\n")
        if tag == "img":
            # El texto alternativo de una imagen también es buscable.
            alt = dict(attrs).get("alt")
            if alt:
                self.partes.append(f" {alt} ")

    def handle_endtag(self, tag):
        if tag in self._IGNORAR and self._dentro:
            self._dentro -= 1

    def handle_data(self, data):
        if not self._dentro:
            self.partes.append(data)


def html(datos: bytes) -> str:
    p = _Html()
    p.feed(a_texto(datos))
    p.close()
    return _compactar("".join(p.partes))


# Grupos RTF que no son texto del documento.
_RTF_SALTAR = {
    "fonttbl", "colortbl", "stylesheet", "listtable", "listoverridetable", "pict", "object",
    "objdata", "themedata", "colorschememapping", "datastore", "latentstyles", "rsidtbl",
    "generator", "xmlnstbl", "filetbl", "revtbl", "pgdsctbl",
}
_RTF_SALTO = {"par", "line", "row", "cell", "page", "sect", "tab"}
_RE_RTF = re.compile(rb"\\([a-zA-Z]{1,32})(-?\d{1,10})? ?|\\'([0-9a-fA-F]{2})|\\(.)|([{}])|([^\\{}]+)", re.DOTALL)


def rtf(datos: bytes) -> str:
    """Texto de un RTF. Las secuencias \\'hh van en Windows-1252; \\uN es Unicode."""
    salida: list[str] = []
    pila: list[tuple[bool, int]] = []
    saltar = False
    uc = 1  # caracteres de sustitución tras \uN
    pendientes = 0
    for m in _RE_RTF.finditer(datos):
        palabra, num, hexa, simbolo, llave, texto = m.groups()
        if llave == b"{":
            pila.append((saltar, uc))
            continue
        if llave == b"}":
            if pila:
                saltar, uc = pila.pop()
            continue
        if palabra is not None:
            p = palabra.decode()
            if p in _RTF_SALTAR:
                saltar = True
            elif p == "uc" and num:
                uc = int(num)
            elif p == "u" and num and not saltar:
                cp = int(num)
                salida.append(chr(cp + 65536 if cp < 0 else cp))
                pendientes = uc
            elif p in _RTF_SALTO and not saltar:
                salida.append("\n" if p != "tab" else "\t")
            continue
        if simbolo is not None:
            if simbolo == b"*":
                saltar = True  # destino opcional ({\*\...}): no es texto visible
            elif simbolo in (b"\\", b"{", b"}") and not saltar:
                salida.append(simbolo.decode())
            elif simbolo == b"~" and not saltar:
                salida.append(" ")
            continue
        if hexa is not None:
            if pendientes:
                pendientes -= 1
            elif not saltar:
                salida.append(bytes([int(hexa, 16)]).decode("cp1252", errors="replace"))
            continue
        if texto and not saltar:
            t = texto.replace(b"\r", b"").replace(b"\n", b"")
            if pendientes:
                quita = min(pendientes, len(t))
                t, pendientes = t[quita:], pendientes - quita
            salida.append(t.decode("cp1252", errors="replace"))
    return _compactar("".join(salida))


def _compactar(texto: str) -> str:
    texto = re.sub(r"[ \t\u00a0]+", " ", texto)
    return re.sub(r"\n\s*\n+", "\n", texto).strip()
