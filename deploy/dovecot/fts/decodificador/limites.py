"""Límites del decodificador de adjuntos: tamaño, descompresión, profundidad, tiempo y memoria.

Un adjunto es lo que alguien de fuera decide mandar. Todo lo que hace el decodificador está acotado
aquí: cuánto lee de la entrada, cuánto puede descomprimir en total (contando los bytes reales, no lo
que dice la cabecera del comprimido), cuántos archivos abre, cuántos niveles de comprimido dentro de
comprimido sigue y cuánto texto devuelve. Los valores se pueden ajustar en
/etc/maquita-fts/decodificador.conf (CLAVE=valor, una por línea); lo que no se entienda se ignora.
"""

import os
import re
from dataclasses import dataclass, field

RUTA_CONF = os.environ.get("MAQUITA_FTS_CONF", "/etc/maquita-fts/decodificador.conf")
MB = 1024 * 1024

_RE_LINEA = re.compile(r"([A-Z_]{2,40})=([0-9]{1,6})")


class LimiteSuperado(Exception):
    """Se pasó un límite: se deja de leer y se devuelve lo extraído hasta ahí."""


@dataclass
class Limites:
    max_entrada: int = 50 * MB  # tamaño máximo del adjunto que se acepta
    max_descomprimido: int = 100 * MB  # bytes reales descomprimidos, sumando todo el adjunto
    max_miembros: int = 2000  # archivos dentro de comprimidos (en total)
    max_profundidad: int = 3  # comprimido dentro de comprimido dentro de…
    max_ratio: int = 500  # descomprimido / comprimido de un miembro de más de 1 MB
    max_texto: int = 4 * MB  # texto que se devuelve a Dovecot
    tiempo_externo: int = 20  # segundos por programa externo (pdftotext, exiftool…)
    memoria: int = 1024 * MB  # memoria virtual del proceso y de sus programas
    ocr: int = 0  # 1 = OCR con Tesseract de PDF escaneados e imágenes
    ocr_paginas: int = 3  # páginas de PDF que pasan por OCR


# Nombre en el archivo de configuración → (campo, multiplicador)
_CLAVES = {
    "MAX_ENTRADA_MB": ("max_entrada", MB),
    "MAX_DESCOMPRIMIDO_MB": ("max_descomprimido", MB),
    "MAX_MIEMBROS": ("max_miembros", 1),
    "MAX_PROFUNDIDAD": ("max_profundidad", 1),
    "MAX_RATIO": ("max_ratio", 1),
    "MAX_TEXTO_MB": ("max_texto", MB),
    "TIEMPO_EXTERNO_S": ("tiempo_externo", 1),
    "MEMORIA_MB": ("memoria", MB),
    "OCR": ("ocr", 1),
    "OCR_PAGINAS": ("ocr_paginas", 1),
}
# Topes duros: ni un archivo de configuración equivocado los pasa.
_TOPES = {
    "max_entrada": 200 * MB,
    "max_descomprimido": 1024 * MB,
    "max_miembros": 20000,
    "max_profundidad": 5,
    "max_ratio": 1000,
    "max_texto": 32 * MB,
    "tiempo_externo": 120,
    "memoria": 4096 * MB,
    "ocr": 1,
    "ocr_paginas": 20,
}


def cargar(ruta: str = RUTA_CONF) -> Limites:
    lim = Limites()
    try:
        with open(ruta, encoding="utf-8", errors="replace") as f:
            lineas = f.read(64 * 1024).splitlines()
    except OSError:
        return lim
    for linea in lineas:
        m = _RE_LINEA.fullmatch(linea.strip())
        if not m or m.group(1) not in _CLAVES:
            continue
        campo, mult = _CLAVES[m.group(1)]
        valor = int(m.group(2)) * mult
        if campo not in ("ocr",) and valor <= 0:
            continue
        setattr(lim, campo, min(valor, _TOPES[campo]))
    return lim


def aplicar_rlimits(lim: Limites) -> None:
    """Memoria, núcleo y archivos del proceso; lo heredan los programas externos."""
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (lim.memoria, lim.memoria))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        # Lo único que se escribe en disco son copias temporales del adjunto y sus miembros.
        tope = lim.max_entrada + lim.max_descomprimido
        resource.setrlimit(resource.RLIMIT_FSIZE, (tope, tope))
    except (ImportError, ValueError, OSError):
        pass


@dataclass
class Presupuesto:
    """Lo que queda por gastar en todo el adjunto, compartido entre niveles de comprimido."""

    lim: Limites
    descomprimido: int = 0
    miembros: int = 0
    texto: list = field(default_factory=list)
    largo_texto: int = 0
    avisos: list = field(default_factory=list)

    def gastar_bytes(self, n: int) -> None:
        self.descomprimido += n
        if self.descomprimido > self.lim.max_descomprimido:
            raise LimiteSuperado("se pasó el límite de bytes descomprimidos")

    def contar_miembro(self) -> None:
        self.miembros += 1
        if self.miembros > self.lim.max_miembros:
            raise LimiteSuperado("demasiados archivos dentro del comprimido")

    def queda_texto(self) -> int:
        return max(0, self.lim.max_texto - self.largo_texto)

    def añadir_texto(self, texto: str) -> None:
        if not texto:
            return
        resto = self.queda_texto()
        if resto <= 0:
            raise LimiteSuperado("se llegó al máximo de texto")
        trozo = texto[:resto]
        self.texto.append(trozo)
        self.largo_texto += len(trozo)
        if len(texto) > resto:
            raise LimiteSuperado("se llegó al máximo de texto")
