# -*- coding: utf-8 -*-
"""
Abrir y guardar el PDF de una edición, sin reescribirlo entero.
================================================================
«mejórame los tiempos de guardado» — el usuario, 29-jul-2026.

Medido sobre una proforma real de 130 páginas (3,02 MB):

    editar la celda (el trabajo de verdad) ......  0,09 s
    reescribir el PDF entero (`tobytes()`) .....   1,29 s   ← el 94 %
    guardado incremental .......................   0,17 s

Un PDF se puede guardar **añadiendo al final** solo los objetos que cambiaron,
que es como lo hacen Acrobat y Word. El documento sigue siendo un PDF válido y
el trabajo deja de depender del tamaño del archivo para depender del tamaño del
cambio. Para poder hacerlo, el documento tiene que estar en un ARCHIVO (PyMuPDF
no guarda incremental sobre memoria), y de ahí este módulo: abre en archivo,
guarda incremental y devuelve lo que haga falta.

Y como el guardado es literalmente «añadir al final», lo que se le puede mandar
al navegador es solo **ese añadido**: pegándolo a la copia que ya tiene, obtiene
el documento nuevo. Son decenas de kB en vez de los 3 MB del PDF entero.

Cada tantas ediciones el archivo se compacta (`COMPACTAR_DESDE`), porque los
añadidos se acumulan; así el documento no engorda sin freno.

Autoría: Equipo de Tecnología Maquita — 2026-07-29
"""

import logging
import os
import tempfile
import time
import uuid

import fitz

logger = logging.getLogger(__name__)

# Los temporales viven segundos: en memoria (`/dev/shm`) si la hay, y si no en
# el temporal de siempre. Nunca guardan nada que deba sobrevivir a la petición.
# Una carpeta por usuario del sistema: FARO corre como 'sistemas', pero las
# pruebas y el mantenimiento se hacen como root, y no deben dejar carpetas que
# el servicio luego no pueda escribir.
_CARPETA = os.path.join('/dev/shm' if os.path.isdir('/dev/shm')
                        else tempfile.gettempdir(),
                        'faro-pdf-trabajo-%d' % os.getuid())

# A partir de este crecimiento sobre el tamaño original, el archivo se compacta
# en vez de seguir añadiendo. 1,6 = el documento puede engordar un 60 % antes de
# pagar una reescritura completa.
COMPACTAR_DESDE = 1.6

# Cuántos añadidos se toleran antes de compactar, se mire como se mire el tamaño.
# Hace falta porque el aviso anterior NO basta: cada petición abre el documento de
# nuevo y toma como "original" lo que el archivo mide EN ESE MOMENTO, así que
# compara un solo añadido contra todo lo ya acumulado y la condición no vuelve a
# cumplirse nunca. Medido en la auditoría del 29-jul-2026: 30 ediciones llevaban
# una proforma de 185 kB a 5.490 kB, casi 30 veces, sin compactar ni una sola vez.
# Contar los añadidos sí es fiable, porque cada uno deja su marca de fin en el
# archivo y esa cuenta no depende de cómo se abriera el documento.
GENERACIONES_MAXIMAS = 5

# Y un tope absoluto, por si un documento con muchas imágenes engorda de golpe.
TOPE_POR_DOCUMENTO = 25 * 1024 * 1024

# Los huérfanos (una petición que se cortó a la mitad) se barren pasado esto.
VIDA_TEMPORAL = 600.0
_ultimo_barrido = [0.0]


class PdfEnRuta(object):
    """Un PDF que ya está en el servidor, nombrado por su ruta.

    Se pasa en lugar del contenido a las operaciones de edición. Así el ayudante
    abre el archivo donde está —sin leerlo entero ni volver a escribirlo— y el
    guardado por añadido ocurre sobre ese mismo archivo, que es lo que hace que
    el cambio devuelto sean decenas de kB en vez de megas.
    """

    __slots__ = ('ruta', 'sello')

    def __init__(self, ruta):
        self.ruta = ruta
        # Con qué se reconoce «este documento, tal como está ahora»: sirve de
        # clave para lo que se recuerda del reconocimiento de tablas, y cambia
        # sola en cuanto el archivo cambia. Es mucho más barata que resumir el
        # contenido entero en cada petición.
        estado = os.stat(ruta)
        self.sello = '%s-%d-%d' % (os.path.basename(ruta), estado.st_size,
                                   estado.st_mtime_ns)

    def __len__(self):
        return os.path.getsize(self.ruta)


def huella_de(contenido_pdf):
    """Con qué se identifica un documento, venga como venga."""
    if isinstance(contenido_pdf, PdfEnRuta):
        return contenido_pdf.sello
    import hashlib
    return hashlib.sha1(contenido_pdf).hexdigest()


def abrir_para_leer(contenido_pdf):
    """El documento, solo para consultarlo (no se va a guardar)."""
    if isinstance(contenido_pdf, PdfEnRuta):
        return fitz.open(contenido_pdf.ruta)
    return fitz.open(stream=contenido_pdf, filetype='pdf')


def _carpeta():
    try:
        os.makedirs(_CARPETA, mode=0o700, exist_ok=True)
    except OSError:
        pass
    return _CARPETA


def _barrer():
    """Borra los temporales que quedaron sueltos. Barato y de tarde en tarde."""
    ahora = time.time()
    if ahora - _ultimo_barrido[0] < 120.0:
        return
    _ultimo_barrido[0] = ahora
    try:
        for nombre in os.listdir(_carpeta()):
            ruta = os.path.join(_CARPETA, nombre)
            try:
                if ahora - os.path.getmtime(ruta) > VIDA_TEMPORAL:
                    os.unlink(ruta)
            except OSError:
                pass
    except OSError:
        pass


def abrir(contenido_pdf=None, ruta=None):
    """El documento listo para editar Y guardar incremental.

    - `ruta`: el PDF ya está en disco (sesión de documento) → se trabaja ahí
      mismo, sin copiar nada.
    - `contenido_pdf`: llegó por la petición → se vuelca a un temporal, que
      cuesta milisegundos y ahorra el segundo largo del guardado.

    Devuelve el documento, con lo que `guardar` necesita saber colgado de él
    (`_faro_estado`), para no tener que ir pasándolo de mano en mano. Quien abre
    es responsable de llamar a `cerrar`.
    """
    _barrer()
    if isinstance(contenido_pdf, PdfEnRuta):
        ruta = contenido_pdf.ruta
    if ruta:
        documento = fitz.open(ruta)
        tam = os.path.getsize(ruta)
        documento._faro_estado = {'ruta': ruta, 'propia': False,
                                  'base': tam, 'original': tam}
        return documento

    if contenido_pdf is None:
        raise ValueError('Hace falta el PDF o su ruta.')
    destino = os.path.join(_carpeta(), '%s.pdf' % uuid.uuid4().hex)
    with open(destino, 'wb') as archivo:
        archivo.write(contenido_pdf)
    documento = fitz.open(destino)
    documento._faro_estado = {'ruta': destino, 'propia': True,
                              'base': len(contenido_pdf),
                              'original': len(contenido_pdf)}
    return documento


# Cómo acabó el último guardado de ESTE proceso. Lo consulta el ayudante para
# saber si puede mandarle al navegador solo el trozo añadido o le tiene que
# mandar el documento entero. Cada ayudante atiende un encargo cada vez, así que
# un dato de módulo es exactamente lo que hace falta y no se pisa con nadie.
_ULTIMO = {'creció_por_añadido': False, 'desde': 0}


def ultimo_guardado():
    """(¿creció por añadido?, desde qué byte) del último guardado."""
    return _ULTIMO['creció_por_añadido'], _ULTIMO['desde']


def _generaciones(ruta):
    """Cuántas veces se le ha añadido algo al documento.

    Cada guardado por añadido deja al final su propia marca de fin de archivo, así
    que basta con contarlas. Se leen solo los últimos kilobytes de cada trozo, no
    el documento entero: da igual que pese megas.
    """
    marcas = 0
    try:
        with open(ruta, 'rb') as archivo:
            resto = b''
            while True:
                trozo = archivo.read(1 << 20)
                if not trozo:
                    break
                marcas += (resto + trozo).count(b'%%EOF')
                resto = trozo[-8:]
    except OSError:
        return 0
    return marcas


def guardar(documento, delta=False):
    """Escribe los cambios y devuelve el PDF (o solo lo añadido).

    Con `delta=True` devuelve `(bytes_añadidos, offset)`: el navegador pega esos
    bytes al final de su copia —si su copia mide `offset`— y ya tiene el
    documento nuevo. Con `delta=False` devuelve el PDF entero, como siempre.

    Si el archivo ha crecido demasiado a fuerza de añadidos, aquí se compacta:
    esa vez cuesta lo que costaba antes, pero es una de cada muchas.
    """
    estado = getattr(documento, '_faro_estado', None)
    if estado is None:
        # Un documento que no pasó por `abrir` (o que ya se guardó): se devuelve
        # entero, como se hacía antes. Nunca se deja al usuario sin su archivo.
        return (documento.tobytes(), 0) if delta else documento.tobytes()

    ruta = estado['ruta']
    antes = estado.get('base') or 0
    compactado = False

    try:
        documento.save(ruta, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
    except (ValueError, RuntimeError, fitz.FileDataError) as excepcion:
        # Documentos que no admiten el añadido (cifrados, reparados al abrir, o
        # con la tabla de referencias tocada). Se reescriben enteros: más lento,
        # pero nunca se pierde el cambio.
        logger.info('guardado incremental no aplicable, se reescribe: %s', excepcion)
        _ULTIMO.update({'creció_por_añadido': False, 'desde': 0})
        completo = documento.tobytes(garbage=3, deflate=True)
        documento.close()
        with open(ruta, 'wb') as archivo:
            archivo.write(completo)
        estado['base'] = len(completo)
        return (completo, 0) if delta else completo

    ahora = os.path.getsize(ruta)
    if (ahora > estado.get('original', ahora) * COMPACTAR_DESDE
            or ahora > TOPE_POR_DOCUMENTO
            or _generaciones(ruta) > GENERACIONES_MAXIMAS):
        # Compactar es reescribir, y PyMuPDF no reescribe sobre el archivo que
        # tiene abierto: se hace al lado y se pone en su sitio de un tirón, para
        # que nadie llegue a ver el documento a medias.
        # Con el número de proceso en el nombre: dos peticiones compactando a la
        # vez usaban el MISMO archivo temporal y una se llevaba por delante a la
        # otra (auditoría del 29-jul-2026).
        provisional = '%s.compacta.%d' % (ruta, os.getpid())
        documento.save(provisional, garbage=4, deflate=True, clean=True)
        documento.close()
        os.replace(provisional, ruta)
        ahora = os.path.getsize(ruta)
        estado['original'] = ahora
        compactado = True

    _ULTIMO.update({'creció_por_añadido': bool(not compactado and antes
                                               and ahora > antes),
                    'desde': antes})
    with open(ruta, 'rb') as archivo:
        if delta and not compactado and antes and ahora > antes:
            archivo.seek(antes)
            trozo = archivo.read()
            estado['base'] = ahora
            return trozo, antes
        completo = archivo.read()

    estado['base'] = ahora
    return (completo, 0) if delta else completo


def cerrar(documento):
    """Suelta el documento y borra el temporal si lo habíamos creado nosotros."""
    estado = getattr(documento, '_faro_estado', None)
    try:
        documento.close()
    except Exception:
        pass
    if estado and estado.get('propia'):
        try:
            os.unlink(estado['ruta'])
        except OSError:
            pass
