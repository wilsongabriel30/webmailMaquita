"""
Plan de un ZIP reanudable (Drive Maquita): qué entra, en qué orden y con qué
tamaño, guardado para que un reintento encuentre EXACTAMENTE el mismo ZIP.

Reanudar solo es válido si el ZIP que se continúa es byte a byte el mismo que
se empezó a bajar. El plan lo garantiza:
  - `firma`  → estado del origen (nombres, tamaños y fechas). Si alguien cambia
    un archivo, la firma cambia y el plan anterior deja de usarse.
  - copias propias → lo que no se entrega tal cual (hojas en forma compatible,
    archivos sin macro) se guarda junto al plan; son pocos y pequeños.
  - `etag`   → identifica el ZIP resultante; el navegador lo devuelve al
    reanudar (If-Range) y, si ya no coincide, la descarga empieza de nuevo.
  - sumas de verificación ya calculadas → un reintento no relee lo enviado.

Todo vive en /tmp/almacen-zip-planes y se borra tras 24 h sin uso. El ZIP en sí
nunca se guarda: se envía en flujo (zip_reanudable.py).
"""
import base64
import hashlib
import json
import logging
import os
import shutil
import time
import uuid
import zlib

from compartido_medios import _en_hilo
from zip_reanudable_formato import Entrada, distribuir

log = logging.getLogger('almacen.zip_reanudable')

_DIR = '/tmp/almacen-zip-planes'
_VIDA = 24 * 3600
_VERSION = 'r1'          # cambia si cambia el formato: invalida planes viejos
_BLOQUE = 4 * 1024 * 1024
_ultima_limpieza = [0.0]


class Plan:
    def __init__(self, entradas, etag):
        self.entradas = entradas
        self.etag = etag
        self.inicio_central, self.tam_central, self.total = distribuir(entradas)


def firma_de(elementos):
    """Firma de [(nombre_en_zip, ruta | None)]: cambia si cambia cualquier
    nombre, tamaño o fecha."""
    huella = hashlib.sha1(_VERSION.encode())
    for nombre, ruta in elementos:
        if ruta is None:
            huella.update(('%s|d\n' % nombre).encode())
            continue
        try:
            estado = os.stat(ruta)
            huella.update(('%s|%d|%d\n' % (nombre, estado.st_size, estado.st_mtime_ns)).encode())
        except OSError:
            huella.update(('%s|?\n' % nombre).encode())
    return huella.hexdigest()


def en_paralelo(funcion, elementos, hilos=4):
    """funcion(x) para cada elemento, en hilos reales y sin congelar el
    worker. Devuelve los resultados en el mismo orden."""
    elementos = list(elementos)
    if not elementos:
        return []
    try:
        from eventlet import GreenPool
    except ImportError:
        return [funcion(x) for x in elementos]
    return list(GreenPool(hilos).imap(lambda x: _en_hilo(funcion, x), elementos))


def crc_de(ruta, tam):
    """CRC de los primeros `tam` bytes. Solo disco y CPU: apto para tpool."""
    crc = 0
    falta = tam
    with open(ruta, 'rb') as f:
        while falta:
            bloque = f.read(min(_BLOQUE, falta))
            if not bloque:
                raise IOError('archivo más corto de lo previsto: %s' % ruta)
            crc = zlib.crc32(bloque, crc)
            falta -= len(bloque)
    return crc


# ── obtener (cargar o armar) ─────────────────────────────────────────────────
def obtener(firma, construir):
    """Plan para esa firma. `construir()` solo se llama si no hay uno vigente
    y devuelve (entradas, temporales):
      entradas   = [(origen, nombre_en_zip[, fecha])], origen: ruta | bytes | None
      temporales = rutas de `entradas` que son copias temporales; pasan a ser
                   del plan (se mueven a su carpeta)."""
    os.makedirs(_DIR, mode=0o700, exist_ok=True)
    _limpiar()
    archivo = os.path.join(_DIR, firma + '.json')
    plan = _cargar(archivo)
    if plan is None:
        plan = _armar(firma, archivo, construir)
    return plan


def _cargar(archivo):
    try:
        with open(archivo, encoding='utf-8') as f:
            datos = json.load(f)
        if datos.get('version') != _VERSION:
            return None
        entradas = []
        for d in datos['entradas']:
            if d.get('p') and os.path.getsize(d['o']) != d['s']:
                return None
            entradas.append(Entrada(
                d['n'], d['t'], d['s'], d['m'], origen=d.get('o'), crc=d.get('c'),
                memoria=base64.b64decode(d['x']) if 'x' in d else None,
                propia=bool(d.get('p'))))
        for ruta in (archivo, datos.get('carpeta')):
            if ruta:
                try:
                    os.utime(ruta)
                except OSError:
                    pass
        return Plan(entradas, datos['etag'])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _armar(firma, archivo, construir):
    crudas, temporales = construir()
    temporales = set(temporales or ())
    carpeta = os.path.join(_DIR, '%s-%s' % (firma, uuid.uuid4().hex[:8]))
    ahora = int(time.time())
    fichas = []
    for numero, cruda in enumerate(crudas):
        origen, nombre = cruda[0], cruda[1].replace(os.sep, '/')
        fecha = cruda[2] if len(cruda) > 2 else None
        if origen is None:
            fichas.append({'n': nombre.rstrip('/') + '/', 't': 'd', 's': 0,
                           'm': fecha or ahora, 'c': 0})
        elif isinstance(origen, bytes):
            fichas.append({'n': nombre, 't': 'm', 's': len(origen), 'm': fecha or ahora,
                           'c': zlib.crc32(origen), 'x': base64.b64encode(origen).decode()})
        else:
            ficha = _ficha_archivo(origen, nombre, fecha, origen in temporales, carpeta, numero)
            if ficha:
                fichas.append(ficha)
    huella = hashlib.sha1(_VERSION.encode())
    for d in fichas:
        huella.update(json.dumps([d['n'], d['t'], d['s'], d['m'], d.get('c')]).encode())
    etag = '"%s"' % huella.hexdigest()
    datos = {'version': _VERSION, 'etag': etag, 'entradas': fichas,
             'carpeta': carpeta if os.path.isdir(carpeta) else None}
    provisional = '%s.%s.tmp' % (archivo, uuid.uuid4().hex[:8])
    with open(provisional, 'w', encoding='utf-8') as f:
        json.dump(datos, f)
    os.replace(provisional, archivo)
    return _cargar(archivo) or Plan([], etag)


def _ficha_archivo(origen, nombre, fecha, es_temporal, carpeta, numero):
    try:
        if es_temporal:
            os.makedirs(carpeta, mode=0o700, exist_ok=True)
            destino = os.path.join(carpeta, '%d%s' % (numero, os.path.splitext(origen)[1]))
            shutil.move(origen, destino)
            origen = destino
        estado = os.stat(origen)
        if not os.path.isfile(origen):
            return None
        ficha = {'n': nombre, 't': 'a', 'o': origen, 's': estado.st_size,
                 'm': fecha or int(estado.st_mtime)}
        if es_temporal:
            ficha['p'] = 1
            ficha['c'] = _en_hilo(crc_de, origen, estado.st_size)
        return ficha
    except OSError as excepcion:
        log.warning('zip reanudable: se omite %s: %s', origen, excepcion)
        return None


# ── sumas de verificación ya calculadas ──────────────────────────────────────
def _archivo_crc(etag):
    return os.path.join(_DIR, etag.strip('"') + '.crc')


def crcs_guardados(etag):
    conocidos = {}
    try:
        with open(_archivo_crc(etag)) as f:
            for linea in f:
                partes = linea.split()
                if len(partes) == 2:
                    conocidos[int(partes[0])] = int(partes[1])
    except (OSError, ValueError):
        pass
    return conocidos


def guardar_crc(etag, indice, crc):
    """Una línea por archivo, añadida de una sola escritura: varios workers
    pueden anotar a la vez sin pisarse."""
    try:
        descriptor = os.open(_archivo_crc(etag), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(descriptor, b'%d %d\n' % (indice, crc))
        finally:
            os.close(descriptor)
    except OSError:
        pass


def _limpiar():
    ahora = time.time()
    if ahora - _ultima_limpieza[0] < 600:
        return
    _ultima_limpieza[0] = ahora
    try:
        nombres = os.listdir(_DIR)
    except OSError:
        return
    for nombre in nombres:
        ruta = os.path.join(_DIR, nombre)
        try:
            if ahora - os.path.getmtime(ruta) < _VIDA:
                continue
            if os.path.isdir(ruta):
                shutil.rmtree(ruta, ignore_errors=True)
            else:
                os.unlink(ruta)
        except OSError:
            pass
