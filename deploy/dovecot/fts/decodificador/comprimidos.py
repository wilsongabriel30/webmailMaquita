"""Comprimidos (ZIP, TAR, gzip, bzip2, xz y 7z) leídos sin escribir nada fuera de la carpeta temporal.

Defensas contra bombas de descompresión:
  - se cuentan los bytes REALES que salen, no el tamaño que declara la cabecera (que miente);
  - un presupuesto común para todo el adjunto (bytes y número de archivos), compartido por todos
    los niveles: un ZIP con mil ZIP dentro gasta del mismo saldo;
  - tope de profundidad (comprimido dentro de comprimido) y de proporción entre lo comprimido y lo
    descomprimido de cada miembro;
  - los miembros cifrados, los enlaces y los dispositivos se saltan.
Nada se extrae a disco con su nombre: el contenido de cada miembro va a memoria (acotado) y de ahí al
decodificador, así que «zip slip» y enlaces que salen de la carpeta no tienen dónde apoyarse.
"""

import bz2
import io
import lzma
import os
import tarfile
import zipfile
import zlib

import externos
from limites import LimiteSuperado, Presupuesto

_TROZO = 1 << 16
_MIEMBRO_PEQUENO = 1024 * 1024


def _tope_miembro(presupuesto: Presupuesto) -> int:
    queda = presupuesto.lim.max_descomprimido - presupuesto.descomprimido
    return max(0, min(queda, presupuesto.lim.max_entrada))


def leer_miembro_zip(zf: zipfile.ZipFile, info: zipfile.ZipInfo, presupuesto: Presupuesto) -> bytes:
    """Contenido de un miembro, contando los bytes reales. b"" si se salta (cifrado, sospechoso)."""
    lim = presupuesto.lim
    if info.is_dir() or info.flag_bits & 0x1:
        return b""
    if info.file_size > _tope_miembro(presupuesto):
        presupuesto.avisos.append(f"{info.filename}: demasiado grande")
        return b""
    # Los miembros pequeños no pueden hacer daño aunque compriman mucho (un XML repetitivo).
    if info.file_size > _MIEMBRO_PEQUENO and info.file_size / max(1, info.compress_size) > lim.max_ratio:
        presupuesto.avisos.append(f"{info.filename}: proporción de compresión sospechosa (bomba)")
        return b""
    salida = bytearray()
    with zf.open(info) as f:
        while True:
            trozo = f.read(_TROZO)
            if not trozo:
                break
            presupuesto.gastar_bytes(len(trozo))
            salida += trozo
            if len(salida) > info.file_size + _TROZO:
                # La cabecera mentía sobre el tamaño: es una bomba o un archivo manipulado.
                raise LimiteSuperado(f"{info.filename}: descomprime más de lo que declara")
    return bytes(salida)


def zip_(zf: zipfile.ZipFile, presupuesto: Presupuesto, recursar) -> None:
    for info in zf.infolist():
        presupuesto.contar_miembro()
        if info.is_dir():
            continue
        presupuesto.añadir_texto(info.filename + "\n")
        datos = leer_miembro_zip(zf, info, presupuesto)
        if datos:
            recursar(datos, os.path.basename(info.filename))


def tar(datos: bytes, presupuesto: Presupuesto, recursar) -> None:
    """Un TAR ya descomprimido (el gzip/xz de un .tar.gz se quita antes, con su propio tope)."""
    with tarfile.open(fileobj=io.BytesIO(datos), mode="r:") as tf:
        for miembro in tf:
            presupuesto.contar_miembro()
            if not miembro.isfile():
                continue  # carpetas, enlaces, dispositivos: nada que leer
            presupuesto.añadir_texto(miembro.name + "\n")
            if miembro.size > _tope_miembro(presupuesto):
                presupuesto.avisos.append(f"{miembro.name}: demasiado grande")
                continue
            f = tf.extractfile(miembro)
            if f is None:
                continue
            contenido = f.read(miembro.size)
            presupuesto.gastar_bytes(len(contenido))
            recursar(contenido, os.path.basename(miembro.name))


def descomprimir(datos: bytes, clase: str, presupuesto: Presupuesto) -> bytes:
    """gzip, bzip2 o xz de un solo flujo (o varios gzip seguidos), con tope de salida."""
    tope = _tope_miembro(presupuesto)
    salida = bytearray()

    def gastar(trozo: bytes) -> None:
        if len(salida) + len(trozo) > tope:
            raise LimiteSuperado("el comprimido descomprime más del máximo permitido")
        presupuesto.gastar_bytes(len(trozo))
        salida.extend(trozo)

    if clase == "gzip":
        resto = datos
        while resto[:2] == b"\x1f\x8b":
            d = zlib.decompressobj(47)
            entrada = resto
            while entrada and not d.eof:
                gastar(d.decompress(entrada, _TROZO))
                entrada = d.unconsumed_tail
            if not d.eof:
                break  # truncado: vale lo que salió
            resto = d.unused_data
        return bytes(salida)
    d = bz2.BZ2Decompressor() if clase == "bzip2" else lzma.LZMADecompressor()
    entrada = datos
    while not d.eof:
        gastar(d.decompress(entrada, max_length=_TROZO))
        entrada = b""
        if d.needs_input:
            break
    return bytes(salida)


def siete_z(ruta: str, presupuesto: Presupuesto, recursar, tmp: str) -> None:
    lim = presupuesto.lim
    for nombre, tam in externos.siete_z_lista(ruta, lim, tmp):
        presupuesto.contar_miembro()
        presupuesto.añadir_texto(nombre + "\n")
        tope = _tope_miembro(presupuesto)
        if tam > tope:
            presupuesto.avisos.append(f"{nombre}: demasiado grande")
            continue
        # El tope de salida es el tamaño declarado (o lo que queda): si miente, se corta.
        contenido = externos.siete_z_miembro(ruta, nombre, lim, tmp, min(tope, tam + _TROZO))
        presupuesto.gastar_bytes(len(contenido))
        if contenido:
            recursar(contenido, os.path.basename(nombre))
