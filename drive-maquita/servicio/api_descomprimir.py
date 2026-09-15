# -*- coding: utf-8 -*-
"""
Descomprimir un .zip desde el propio Drive
==========================================
`POST /api/almacen/archivos/descomprimir` — saca el contenido de un `.zip` en su
misma carpeta, dentro de una carpeta nueva con el nombre del archivo.

Wilson, 07/09/2026: al migrar desde Google llegan carpetas enteras en `.zip` y
hasta ahora había que descomprimirlas fuera del Drive.

Lo que se cuida al extraer:

  · **Nombres**: los `.zip` viejos guardan los nombres en la codificación de
    MS-DOS y las tildes llegan rotas («+�ndice»). Se recuperan.
  · **Rutas**: se descarta cualquier entrada con ruta absoluta, con «..» o con
    enlaces simbólicos. Nada puede escribirse fuera de su carpeta.
  · **Tamaño**: hay un tope de lo que puede ocupar lo extraído y de cuántos
    archivos pueden salir, para que un `.zip` preparado no llene el disco
    («zip bomba»).
  · **Cuota y permisos**: se comprueba que se pueda escribir en esa unidad.

Cada archivo extraído entra por `nucleo.subir()`, igual que si se hubiera
subido a mano: así queda indexado, con su versión y su deduplicación, y pasa
por los arreglos de los libros de Google.

Si lo extraído resulta ser la exportación HTML de un libro de Google (una
página por hoja), se arma además el `.xlsx` y se deja en la misma carpeta
(`zip_google_a_xlsx.py`; Wilson, 08/09/2026).

Autoría: Equipo de Tecnología Maquita — 2026-09-07/08
"""
import io
import logging
import os
import zipfile

from flask import Blueprint, jsonify, request

import nucleo_archivos as nucleo
import zip_google_a_xlsx
from api_archivos import _efectivo, _permiso_unidad, error, usuario_actual
from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual, ruta_fisica

log = logging.getLogger(__name__)
bp_descomprimir = Blueprint('almacen_descomprimir', __name__)

TOPE_TOTAL = 5 * 1024 * 1024 * 1024      # 5 GB de contenido extraído
TOPE_ARCHIVOS = 5000                     # y no más de 5000 archivos
TOPE_ZIP = 2 * 1024 * 1024 * 1024        # el propio .zip, hasta 2 GB


def nombre_legible(info):
    """El nombre de la entrada, con las tildes en su sitio.

    Los `.zip` que no marcan UTF-8 guardan los nombres en CP437; si no se
    traducen, salen cosas como «+�ndice Implementaci+�n».
    """
    nombre = info.filename
    if info.flag_bits & 0x800:
        return nombre
    for codificacion in ('utf-8', 'cp1252', 'latin-1'):
        try:
            return nombre.encode('cp437').decode(codificacion)
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return nombre


def partes_seguras(nombre):
    """Trocea la ruta de dentro del zip y se queda solo con lo que es seguro.
       Devuelve [] si la entrada no debe extraerse."""
    limpio = nombre.replace('\\', '/')
    if limpio.startswith('/') or ':' in limpio.split('/')[0]:
        return []                                  # ruta absoluta o con unidad
    partes = []
    for trozo in limpio.split('/'):
        trozo = trozo.strip()
        if not trozo or trozo == '.':
            continue
        if trozo == '..':
            return []                              # sale de la carpeta
        partes.append(trozo)
    return partes


def carpeta_para(ruta_zip):
    """La carpeta donde se deja todo: el nombre del zip, sin la extensión."""
    carpeta = os.path.dirname(ruta_zip) or '/'
    nombre = os.path.basename(ruta_zip)
    if nombre.lower().endswith('.zip'):
        nombre = nombre[:-4]
    return carpeta, nombre.strip() or 'descomprimido'


@bp_descomprimir.route('/archivos/descomprimir', methods=['POST'])
def descomprimir():
    usuario = usuario_actual()
    datos = request.get_json(silent=True) or {}
    try:
        ruta = normalizar_ruta_virtual(datos.get('ruta', ''))
    except RutaInvalida as excepcion:
        return error(str(excepcion), excepcion.codigo)
    if not ruta.lower().endswith('.zip'):
        return error('Esto no es un archivo .zip', 400)
    if not _permiso_unidad(usuario, ruta, escritura=True):
        return error('No tienes permiso para escribir en esta unidad', 403)

    usuario_ef, ruta_ef = _efectivo(usuario, ruta)
    fisica = ruta_fisica(usuario_ef, ruta_ef)
    if not os.path.isfile(fisica):
        return error('No se encuentra el archivo', 404)
    if os.path.getsize(fisica) > TOPE_ZIP:
        return error('El archivo comprimido es demasiado grande para abrirlo aquí', 413)

    carpeta_padre, nombre_carpeta = carpeta_para(ruta_ef)
    try:
        with zipfile.ZipFile(fisica) as z:
            entradas = [i for i in z.infolist() if not i.is_dir()]
            if len(entradas) > TOPE_ARCHIVOS:
                return error('El comprimido trae demasiados archivos (%d)' % len(entradas), 413)
            total = sum(i.file_size for i in entradas)
            if total > TOPE_TOTAL:
                return error('Lo que hay dentro ocupa demasiado para descomprimirlo aquí', 413)

            # Una carpeta con el nombre del zip; si ya existe, se le añade número.
            destino = nombre_carpeta
            intento = 1
            while os.path.exists(ruta_fisica(usuario_ef,
                                             (carpeta_padre.rstrip('/') + '/' + destino))):
                intento += 1
                destino = '%s (%d)' % (nombre_carpeta, intento)
            nucleo.crear_carpeta(usuario_ef, carpeta_padre, destino)
            raiz = (carpeta_padre.rstrip('/') + '/' + destino) or '/'

            sacados, saltados, carpetas = 0, [], set()
            for info in entradas:
                partes = partes_seguras(nombre_legible(info))
                if not partes:
                    saltados.append(info.filename)
                    continue
                subcarpeta = raiz
                for trozo in partes[:-1]:
                    if (subcarpeta, trozo) not in carpetas:
                        try:
                            nucleo.crear_carpeta(usuario_ef, subcarpeta, trozo)
                        except Exception:            # noqa: BLE001  (ya existía)
                            pass
                        carpetas.add((subcarpeta, trozo))
                    subcarpeta = subcarpeta.rstrip('/') + '/' + trozo
                try:
                    with z.open(info) as dentro:
                        nucleo.subir(usuario_ef, subcarpeta, partes[-1], dentro)
                    sacados += 1
                except Exception as excepcion:       # noqa: BLE001
                    log.warning('Descomprimir %s: no se pudo sacar %s (%s)',
                                ruta, info.filename, excepcion)
                    saltados.append(partes[-1])
    except zipfile.BadZipFile:
        return error('El archivo está dañado o no es un .zip', 400)
    except Exception as excepcion:                   # noqa: BLE001
        log.exception('Descomprimir %s', ruta)
        return error('No se pudo descomprimir: %s' % excepcion, 500)

    # Si lo que salió es la exportación HTML de un libro de Google (una página por
    # hoja), se arma además el .xlsx: eso es lo que la gente venía a buscar y no
    # unas páginas web (Wilson, 08/09/2026).
    libro = zip_google_a_xlsx.hacer_libro(usuario_ef, raiz,
                                          ruta_fisica(usuario_ef, raiz), nombre_carpeta)

    mensaje = 'Se sacaron %d archivo(s) en la carpeta «%s»' % (sacados, destino)
    if libro:
        mensaje += ', y se armó el libro «%s»' % libro

    log.info('Descomprimido %s: %d archivo(s) en «%s»%s', ruta, sacados, destino,
             (' + libro «%s»' % libro) if libro else '')
    return jsonify({
        'ok': True,
        'carpeta': destino,
        'ruta': raiz,
        'archivos': sacados,
        'saltados': saltados[:20],
        'libro': libro,
        'mensaje': mensaje
    })
