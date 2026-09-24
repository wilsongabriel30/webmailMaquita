"""
Medios de los enlaces públicos del Drive (/almacen-s/<token>/...).

- Fotos livianas: miniatura (cuadrícula, 400 px) y vista previa (visor,
  1600 px), en JPEG con la orientación de la cámara corregida y en caché.
  Antes /thumb/ y el visor enviaban la foto ORIGINAL (varios MB cada una):
  una carpeta de 159 fotos tardaba en pintar y el «siguiente» del visor
  hacía esperar a cada foto.
- ZIP de «Descargar todo»: los formatos ya comprimidos (fotos, vídeo,
  Office, PDF…) se guardan sin volver a comprimir, el trabajo va en un hilo
  aparte y el resultado queda en caché dos horas para quien descargue la
  misma carpeta después.

FARO corre con workers eventlet: una tarea larga de CPU dentro del worker
congela a todas las peticiones que atiende. Por eso el trabajo pesado va por
tpool (hilo del sistema operativo).

Separado de integracion_faro.py (ya pasa de 1.000 líneas) — 24/09/2026.
"""
import hashlib
import logging
import os
import re
import shutil
import time
import uuid
import zipfile

log = logging.getLogger('almacen.compartido_medios')

LADOS = {'thumb': 400, 'previa': 1600}
_CACHE_IMAGENES = '/tmp/almacen-previews'
_CACHE_ZIP = '/tmp/almacen-zip-publico'
_ZIP_VIDA_SEGUNDOS = 2 * 3600
_ZIP_LIBRE_MINIMO = 20 * 1024 ** 3   # sin este espacio libre, el ZIP no se guarda

# Volver a comprimir estos formatos gasta CPU y no ahorra ni un byte.
_YA_COMPRIMIDOS = {
    'jpg', 'jpeg', 'png', 'gif', 'webp', 'heic', 'heif', 'avif',
    'mp4', 'mov', 'avi', 'mkv', 'webm', 'm4v', '3gp',
    'mp3', 'm4a', 'aac', 'ogg', 'opus', 'flac',
    'zip', 'rar', '7z', 'gz', 'bz2', 'xz', 'tgz',
    'docx', 'xlsx', 'pptx', 'docm', 'xlsm', 'pptm', 'odt', 'ods', 'odp',
    'pdf',
}

_AVISO_VALIDO = re.compile(r'^[A-Za-z0-9]{6,32}$')


def _en_hilo(funcion, *args):
    """Ejecuta `funcion` en un hilo real para no congelar el worker eventlet."""
    try:
        from eventlet import tpool
    except ImportError:
        return funcion(*args)
    return tpool.execute(funcion, *args)


def _extension(nombre):
    return nombre.rsplit('.', 1)[-1].lower() if '.' in nombre else ''


# ── Fotos ────────────────────────────────────────────────────────────────────

def _reducir(fisica, lado):
    mtime = int(os.path.getmtime(fisica))
    clave = hashlib.sha1(f'{fisica}:{mtime}:publico:{lado}'.encode()).hexdigest()
    salida = os.path.join(_CACHE_IMAGENES, clave + '.jpg')
    if os.path.exists(salida):
        return salida
    os.makedirs(_CACHE_IMAGENES, exist_ok=True)
    from PIL import Image, ImageOps
    temporal = f'{salida}.{uuid.uuid4().hex}.tmp'
    with Image.open(fisica) as original:
        # En JPEG, draft() decodifica ya reducido: mucho más rápido en fotos de cámara.
        original.draft('RGB', (lado, lado))
        imagen = ImageOps.exif_transpose(original)
        imagen.thumbnail((lado, lado), Image.LANCZOS)
        if imagen.mode in ('RGBA', 'LA', 'P'):
            imagen = imagen.convert('RGBA')
            fondo = Image.new('RGB', imagen.size, (255, 255, 255))
            fondo.paste(imagen, mask=imagen.split()[-1])
            imagen = fondo
        elif imagen.mode not in ('RGB', 'L'):
            imagen = imagen.convert('RGB')
        imagen.save(temporal, 'JPEG', quality=80, optimize=True, progressive=True)
    os.replace(temporal, salida)
    return salida


def entregar_imagen(destino, modo):
    """Respuesta para /thumb/ y /previa/: la foto reducida, o la original si
    es vectorial/animada o si no se pudo reducir."""
    from flask import send_file
    if _extension(destino) in ('svg', 'gif'):
        return send_file(destino, max_age=86400)
    try:
        ruta = _en_hilo(_reducir, destino, LADOS[modo])
    except Exception as excepcion:
        log.warning('No se pudo reducir %s: %s', destino, excepcion)
        return send_file(destino, max_age=86400)
    return send_file(ruta, mimetype='image/jpeg', max_age=86400)


# ── ZIP de «Descargar todo» ──────────────────────────────────────────────────

def medir_carpeta(destino):
    """(bytes totales, firma del contenido). La firma cambia si cambia
    cualquier archivo, así la caché nunca entrega un ZIP viejo."""
    total = 0
    huella = hashlib.sha1(destino.encode())
    for carpeta, dirs, archivos in os.walk(destino):
        dirs.sort()
        for nombre in sorted(archivos):
            completo = os.path.join(carpeta, nombre)
            try:
                estado = os.stat(completo)
            except OSError:
                continue
            total += estado.st_size
            huella.update(f'{os.path.relpath(completo, destino)}|{estado.st_size}|'
                          f'{int(estado.st_mtime)}\n'.encode())
    return total, huella.hexdigest()


def _limpiar_cache_zip():
    ahora = time.time()
    try:
        entradas = os.listdir(_CACHE_ZIP)
    except OSError:
        return
    for nombre in entradas:
        ruta = os.path.join(_CACHE_ZIP, nombre)
        try:
            if ahora - os.path.getmtime(ruta) > _ZIP_VIDA_SEGUNDOS:
                os.unlink(ruta)
        except OSError:
            pass


def zip_en_cache(firma):
    _limpiar_cache_zip()
    ruta = os.path.join(_CACHE_ZIP, firma + '.zip')
    return ruta if os.path.isfile(ruta) else None


def _planear_zip(destino, base, comp):
    """Lista lo que entra al ZIP. Política de macros: cada archivo con macros
    entra como su COPIA LIMPIA (mismos datos y fórmulas, sin la macro). Los
    que no se pueden limpiar no entran y se listan en un aviso dentro del
    propio ZIP. Corre en el worker (no en tpool) porque la limpieza de
    formatos antiguos puede llamar por red al servidor de conversión."""
    import compartir_macros
    entradas, temporales, omitidos, limpiados = [], [], [], []
    for carpeta, _dirs, archivos in os.walk(destino):
        for nombre in archivos:
            completo = os.path.join(carpeta, nombre)
            relativo = os.path.relpath(completo, destino)
            if not compartir_macros.con_macros(completo, nombre):
                entradas.append((completo, relativo))
                continue
            virtual = None
            try:
                from seguridad_rutas import normalizar_ruta_virtual
                virtual = normalizar_ruta_virtual(
                    comp['ruta'] + '/' + os.path.relpath(completo, base))
            except Exception:
                virtual = None
            ruta_ok, nombre_ok, tmp = compartir_macros.entrega_segura(
                completo, nombre, comp['propietario_id'], virtual)
            if not ruta_ok:
                omitidos.append(relativo)
                continue
            entradas.append((ruta_ok, os.path.join(os.path.dirname(relativo), nombre_ok)))
            limpiados.append(relativo)
            if tmp:
                temporales.append(tmp)
    aviso = None
    if omitidos or limpiados:
        lineas = ['Archivos con macros de la Fundación Maquita', '']
        if limpiados:
            lineas.append('Se incluyeron SIN la macro (conservan datos, '
                          'fórmulas y formato):')
            lineas += ['  - ' + x for x in limpiados] + ['']
        if omitidos:
            lineas.append('NO se incluyeron (no se pudo quitarles la macro). '
                          'Pídelos a quien te compartió el enlace:')
            lineas += ['  - ' + x for x in omitidos]
        aviso = '\n'.join(lineas)
    return entradas, temporales, aviso


def _escribir_zip(salida, entradas, aviso):
    """Solo disco y CPU: apto para correr en tpool."""
    with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        for origen, nombre_zip in entradas:
            z.write(origen, nombre_zip, compress_type=_compresion(nombre_zip))
        if aviso:
            z.writestr('LEEME - archivos con macros.txt', aviso.encode('utf-8'))


def _compresion(nombre):
    return zipfile.ZIP_STORED if _extension(nombre) in _YA_COMPRIMIDOS else zipfile.ZIP_DEFLATED


def armar_zip(destino, base, comp, firma, total):
    """Devuelve (ruta del ZIP, es_temporal). Si hay espacio, el ZIP queda en
    caché; si no, es un temporal que hay que borrar tras enviarlo."""
    os.makedirs(_CACHE_ZIP, exist_ok=True)
    temporal = os.path.join(_CACHE_ZIP, f'.{firma}.{uuid.uuid4().hex}.tmp')
    entradas, limpias, aviso = _planear_zip(destino, base, comp)
    try:
        _en_hilo(_escribir_zip, temporal, entradas, aviso)
    except Exception:
        try:
            os.unlink(temporal)
        except OSError:
            pass
        raise
    finally:
        for copia in limpias:
            try:
                os.unlink(copia)
            except OSError:
                pass
    if shutil.disk_usage(_CACHE_ZIP).free - total > _ZIP_LIBRE_MINIMO:
        definitivo = os.path.join(_CACHE_ZIP, firma + '.zip')
        os.replace(temporal, definitivo)
        return definitivo, False
    return temporal, True


def marcar_aviso(respuesta, aviso):
    """Cookie que la página lee para saber que la descarga ya empezó y cerrar
    el aviso de «Preparando la descarga…»."""
    if aviso and _AVISO_VALIDO.match(aviso):
        respuesta.set_cookie('almacen_zip_' + aviso, '1', max_age=300, path='/',
                             secure=True, samesite='Lax')
    return respuesta
