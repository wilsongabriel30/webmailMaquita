"""Texto de documentos de Office (DOCX, XLSX, PPTX y sus variantes con macros) y de LibreOffice (ODT,
ODS, ODP).

Son ZIP con XML dentro: se leen con zipfile y un lector XML incremental, sin LibreOffice ni nada que
interprete el documento. Las macros (vbaProject.bin, Basic/) no se abren. Un XML con DOCTYPE o
entidades propias se descarta entero: es la puerta de las bombas de entidades («billion laughs») y
ningún documento legítimo de Office las necesita.
"""

import re
import xml.etree.ElementTree as ET
import zipfile

from comprimidos import leer_miembro_zip
from limites import Presupuesto

_RE_PELIGRO = re.compile(rb"<!(DOCTYPE|ENTITY)", re.IGNORECASE)

# Qué partes del documento tienen texto, por orden de interés.
_PARTES_OOXML = [
    re.compile(r"docProps/core\.xml"),
    re.compile(r"word/(document|footnotes|endnotes|comments|header\d*|footer\d*)\.xml"),
    re.compile(r"xl/sharedStrings\.xml"),
    re.compile(r"xl/worksheets/sheet\d+\.xml"),
    re.compile(r"ppt/slides/slide\d+\.xml"),
    re.compile(r"ppt/notesSlides/notesSlide\d+\.xml"),
]
_PARTES_ODF = [re.compile(r"meta\.xml"), re.compile(r"content\.xml")]

# Etiquetas (nombre local) cuyo texto es contenido, y las que cortan párrafo.
_TEXTO_OOXML = {"t", "v", "title", "subject", "creator", "keywords", "description", "lastModifiedBy"}
_PARRAFO = {"p", "br", "tab", "row", "c", "tr", "h", "list-item", "table-cell"}


def _local(etiqueta: str) -> str:
    return etiqueta.rsplit("}", 1)[-1]


class _Recolector:
    """Destino del lector XML: recibe el texto en el orden del documento, sin construir el árbol."""

    def __init__(self, etiquetas: set | None):
        self.etiquetas = etiquetas
        self.pila: list[str] = []
        self.partes: list[str] = []
        # En XLSX, el <v> de una celda de texto es solo el número de su cadena compartida.
        self.celda_compartida = False

    def start(self, etiqueta, atributos):
        nombre = _local(etiqueta)
        self.pila.append(nombre)
        if nombre == "c":
            self.celda_compartida = atributos.get("t") == "s"
        if nombre in _PARRAFO:
            self.partes.append("\n")

    def end(self, etiqueta):
        if self.pila:
            self.pila.pop()

    def data(self, datos):
        if self.celda_compartida and self.pila and self.pila[-1] == "v":
            return
        if self.etiquetas is None or (self.pila and self.pila[-1] in self.etiquetas):
            self.partes.append(datos)

    def close(self):
        return "".join(self.partes)


def texto_xml(datos: bytes, etiquetas: set | None) -> str:
    """Texto de un XML. `etiquetas` = nombres locales con texto; None = todo el texto (ODF)."""
    if _RE_PELIGRO.search(datos):
        return ""
    recolector = _Recolector(etiquetas)
    lector = ET.XMLParser(target=recolector)
    try:
        for i in range(0, len(datos), 1 << 16):
            lector.feed(datos[i : i + (1 << 16)])
        lector.close()
    except ET.ParseError:
        pass  # XML dañado: vale lo leído hasta el error
    return re.sub(r"\n\s*\n+", "\n", "".join(recolector.partes)).strip()


def documento(zf: zipfile.ZipFile, clase: str, presupuesto: Presupuesto) -> None:
    """Añade al presupuesto el texto de un documento OOXML u ODF ya abierto."""
    patrones = _PARTES_OOXML if clase == "ooxml" else _PARTES_ODF
    etiquetas = _TEXTO_OOXML if clase == "ooxml" else None
    infos = {i.filename: i for i in zf.infolist()[: presupuesto.lim.max_miembros]}
    for patron in patrones:
        for nombre in sorted(n for n in infos if patron.fullmatch(n)):
            presupuesto.contar_miembro()
            datos = leer_miembro_zip(zf, infos[nombre], presupuesto)
            if datos:
                presupuesto.añadir_texto(texto_xml(datos, etiquetas) + "\n")
