"""Programas libres del sistema para lo que Python no lee solo: PDF, Office antiguo, 7z, EXIF y OCR.

Cada llamada va con tiempo máximo, salida acotada, entorno vacío y sin shell. Si el programa no está
instalado, simplemente no hay texto de ese formato. Ninguno ejecuta macros ni código del documento:
pdftotext (poppler-utils), catdoc/xls2csv/catppt (catdoc), 7z (7zip), exiftool y tesseract.
"""

import os
import selectors
import shutil
import subprocess
import time

from limites import Limites, LimiteSuperado

_ENTORNO = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}


def disponible(programa: str) -> str | None:
    return shutil.which(programa, path=_ENTORNO["PATH"])


def ejecutar(orden: list[str], lim: Limites, max_salida: int, directorio: str | None = None) -> bytes:
    """Salida estándar de `orden`, como mucho `max_salida` bytes y `lim.tiempo_externo` segundos.

    Si se pasa de la salida se corta el programa y se lanza LimiteSuperado: un miembro de un 7z
    que dice ocupar poco y suelta gigas no llega a escribirse entero en ningún sitio.
    """
    entorno = dict(_ENTORNO, HOME=directorio or "/nonexistent", TMPDIR=directorio or "/tmp")
    proc = subprocess.Popen(
        orden,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        cwd=directorio,
        env=entorno,
        close_fds=True,
        start_new_session=True,
    )
    trozos, total = [], 0
    try:
        fin = time.monotonic() + lim.tiempo_externo
        sel = selectors.DefaultSelector()
        sel.register(proc.stdout, selectors.EVENT_READ)
        while True:
            queda = fin - time.monotonic()
            if queda <= 0:
                raise TimeoutError(f"{os.path.basename(orden[0])} tardó demasiado")
            if not sel.select(timeout=queda):
                continue
            trozo = os.read(proc.stdout.fileno(), 65536)
            if not trozo:
                break
            total += len(trozo)
            if total > max_salida:
                raise LimiteSuperado(f"{os.path.basename(orden[0])}: salida demasiado grande")
            trozos.append(trozo)
        proc.wait(timeout=max(1.0, fin - time.monotonic()))
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        proc.stdout.close()
    return b"".join(trozos)


def pdf_texto(ruta: str, lim: Limites, tmp: str) -> str:
    prog = disponible("pdftotext")
    if not prog:
        return ""
    return ejecutar([prog, "-q", "-enc", "UTF-8", "-l", "500", ruta, "-"], lim, lim.max_texto, tmp).decode(
        "utf-8", errors="replace"
    )


def ocr_pdf(ruta: str, lim: Limites, tmp: str) -> str:
    """OCR de las primeras páginas de un PDF escaneado (solo si OCR=1 en la configuración)."""
    pdftoppm, tesseract = disponible("pdftoppm"), disponible("tesseract")
    if not (lim.ocr and pdftoppm and tesseract):
        return ""
    prefijo = os.path.join(tmp, "pagina")
    ejecutar([pdftoppm, "-q", "-r", "150", "-gray", "-png", "-l", str(lim.ocr_paginas), ruta, prefijo], lim, 1, tmp)
    textos = []
    for nombre in sorted(os.listdir(tmp)):
        if nombre.startswith("pagina") and nombre.endswith(".png"):
            textos.append(ocr_imagen(os.path.join(tmp, nombre), lim, tmp))
    return "\n".join(t for t in textos if t)


def ocr_imagen(ruta: str, lim: Limites, tmp: str) -> str:
    tesseract = disponible("tesseract")
    if not (lim.ocr and tesseract):
        return ""
    return ejecutar([tesseract, ruta, "stdout", "-l", "spa+eng", "--psm", "3"], lim, lim.max_texto, tmp).decode(
        "utf-8", errors="replace"
    )


_OLE = {"doc": "catdoc", "xls": "xls2csv", "ppt": "catppt"}


def office_antiguo(ruta: str, extension: str, lim: Limites, tmp: str) -> str:
    """Word, Excel y PowerPoint 97-2003 con las herramientas de catdoc (no ejecutan macros)."""
    prog = disponible(_OLE.get(extension, "catdoc"))
    if not prog:
        return ""
    return ejecutar([prog, "-d", "utf-8", ruta], lim, lim.max_texto, tmp).decode("utf-8", errors="replace")


# Metadatos de imagen que sirven para buscar: título, autor, cámara, fecha, lugar, palabras clave.
_EXIF = [
    "-Title", "-Description", "-ImageDescription", "-Subject", "-Keywords", "-XPTitle", "-XPSubject",
    "-XPKeywords", "-XPComment", "-UserComment", "-Artist", "-Creator", "-Author", "-Copyright",
    "-Make", "-Model", "-Software", "-DateTimeOriginal", "-CreateDate", "-GPSPosition",
]


def exif(ruta: str, lim: Limites, tmp: str) -> str:
    prog = disponible("exiftool")
    if not prog:
        return ""
    salida = ejecutar([prog, "-q", "-q", "-S", "-fast2", "-charset", "utf8", *_EXIF, "--", ruta], lim, 256 * 1024, tmp)
    return salida.decode("utf-8", errors="replace")


def siete_z_lista(ruta: str, lim: Limites, tmp: str) -> list[tuple[str, int]]:
    """Archivos (ruta, tamaño declarado) de un 7z; las carpetas y los cifrados no se listan."""
    prog = disponible("7z")
    if not prog:
        return []
    salida = ejecutar([prog, "l", "-slt", "-ba", "-p", "--", ruta], lim, 8 * 1024 * 1024, tmp)
    miembros, actual = [], {}
    for linea in salida.decode("utf-8", errors="replace").splitlines() + [""]:
        if not linea.strip():
            if actual.get("Path") and "D" not in actual.get("Attributes", "") and actual.get("Encrypted") != "+":
                tam = actual.get("Size", "0")
                miembros.append((actual["Path"], int(tam) if tam.isdigit() else 0))
            actual = {}
            continue
        if " = " in linea:
            clave, valor = linea.split(" = ", 1)
            actual[clave.strip()] = valor
    return miembros


def siete_z_miembro(ruta: str, miembro: str, lim: Limites, tmp: str, max_bytes: int) -> bytes:
    prog = disponible("7z")
    if not prog:
        return b""
    return ejecutar([prog, "x", "-so", "-p", "-spd", "--", ruta, miembro], lim, max_bytes, tmp)
