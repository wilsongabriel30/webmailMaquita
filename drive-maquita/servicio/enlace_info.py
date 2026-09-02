# -*- coding: utf-8 -*-
"""Qué hay al otro lado de un enlace del Drive Maquita.

Responsabilidad ÚNICA: dada una dirección web, decir si apunta a este Drive y,
si la persona tiene acceso, contar lo que hay allí — nombre, si es carpeta o
archivo, de quién es, cuánto pesa, cuándo se tocó por última vez.

Lo usa la tarjeta que sale al pulsar un enlace en una hoja de cálculo. Hasta
ahora esa tarjeta solo podía decir lo que se deduce de la dirección; con los
enlaces del propio Drive **los datos son nuestros**, así que se muestran de
verdad, como hace Google con los suyos.

REGLA DE ORO: esto no puede convertirse en una rendija para mirar lo ajeno. Se
comprueba el permiso ANTES de contar nada, con las mismas funciones que usa el
explorador, y si no hay acceso se responde que no se tiene — sin filtrar
siquiera si el archivo existe.
"""

import logging
import os
import re
from urllib.parse import urlparse, parse_qs, unquote

from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual, ruta_fisica, unidad_de_ruta

log = logging.getLogger('almacen.enlace_info')

# Las dos puertas del mismo sistema (ver explorador-enlaces-dominio.js).
DOMINIOS = ('drive.maquita.com.ec', 'datos.maquita.com.ec')

# Páginas que abren UN archivo; la ruta viaja en ?ruta=
_VISORES = ('editar', 'diagrama', 'plano', 'formulario', 'formulario-respuestas')

_RE_PUBLICO = re.compile(r'^/(?:s|almacen-s)/([A-Za-z0-9_-]{6,})')


def es_de_maquita(url: str) -> bool:
    try:
        return (urlparse(url).hostname or '').lower() in DOMINIOS
    except Exception:
        return False


def leer_enlace(url: str):
    """Traduce la dirección a lo que señala, sin tocar el disco todavía.

    Devuelve un diccionario con `clase` ('archivo', 'carpeta', 'publico') y la
    ruta o el token, o None si la dirección no es de este Drive o no apunta a
    ningún contenido concreto.
    """
    if not es_de_maquita(url):
        return None
    try:
        partes = urlparse(url)
    except Exception:
        return None
    camino = unquote(partes.path or '')

    publico = _RE_PUBLICO.match(camino)
    if publico:
        return {'clase': 'publico', 'token': publico.group(1)}

    if not camino.startswith('/archivos-almacen'):
        return None
    resto = camino[len('/archivos-almacen'):].strip('/')

    if resto in _VISORES:
        ruta = (parse_qs(partes.query or '').get('ruta') or [''])[0]
        if not ruta:
            return None
        return {'clase': 'archivo', 'ruta': normalizar_ruta_virtual(ruta)}

    if not resto:
        return None                       # la portada del Drive, no un contenido
    return {'clase': 'carpeta', 'ruta': normalizar_ruta_virtual('/' + resto)}


def _puede_ver(usuario_id: int, ruta: str) -> bool:
    """El mismo veredicto que usa el explorador para dejar entrar."""
    try:
        from permisos_compartidos import permiso_compartido
        veredicto = permiso_compartido(usuario_id, ruta, False)
        if veredicto is not None:
            return veredicto
        from api_unidades import permiso_unidad
        return permiso_unidad(usuario_id, ruta, False)
    except Exception as excepcion:
        # Un fallo al comprobar NO puede conceder acceso: falla cerrado.
        log.warning('No se pudo comprobar el permiso de %s: %s', ruta, excepcion)
        return False


def _donde_vive(usuario_id: int, ruta: str) -> dict:
    """En qué espacio del Drive está, y de quién es."""
    unidad_id, _sub = unidad_de_ruta(ruta)
    if unidad_id:
        nombre_unidad, dueno_id = '', None
        try:
            from almacen_bd import consultar
            filas = consultar('SELECT nombre, creado_por FROM unidades_compartidas '
                              'WHERE id = %s', (unidad_id,))
            if filas:
                nombre_unidad = filas[0]['nombre']
                dueno_id = filas[0]['creado_por']
        except Exception as excepcion:
            log.warning('No se pudo leer la unidad %s: %s', unidad_id, excepcion)
        donde = f'Unidad compartida «{nombre_unidad}»' if nombre_unidad \
                else 'Unidad compartida'
        # En la raíz de la unidad la carpeta no tiene nombre propio: se llama
        # como la unidad, no como su número interno.
        raiz = _sub in ('', '/')
        return {'donde': donde, 'propietario_id': dueno_id,
                'nombre_raiz': nombre_unidad if raiz else ''}

    try:
        from permisos_compartidos import compartido_de_ruta
        dueno_id, _ = compartido_de_ruta(ruta)
    except Exception:
        dueno_id = None
    if dueno_id:
        return {'donde': 'Compartido contigo', 'propietario_id': int(dueno_id)}

    return {'donde': 'Mi unidad', 'propietario_id': int(usuario_id)}


def _nombre_de(usuario_id):
    if not usuario_id:
        return ''
    try:
        from vista_compartidos import _nombres_de
        ficha = _nombres_de({int(usuario_id)}).get(int(usuario_id)) or {}
        return ficha.get('nombre') or ficha.get('email') or ''
    except Exception as excepcion:
        log.warning('No se pudo resolver el nombre de %s: %s', usuario_id, excepcion)
        return ''


def peso_legible(bytes_):
    """1536 -> '1,5 KB'. Con coma decimal, que es como se escribe en español."""
    try:
        tamano = float(bytes_)
    except (TypeError, ValueError):
        return ''
    for unidad in ('bytes', 'KB', 'MB', 'GB', 'TB'):
        if tamano < 1024 or unidad == 'TB':
            if unidad == 'bytes':
                return f'{int(tamano)} bytes'
            return f'{tamano:.1f}'.replace('.', ',') + ' ' + unidad
        tamano /= 1024
    return ''


def _cuantos_dentro(fisica: str, tope: int = 200):
    """Cuántos elementos hay en la carpeta. Se deja de contar en `tope`: la
    tarjeta dice «más de 200» y nadie espera por una carpeta enorme."""
    try:
        cuenta = 0
        with os.scandir(fisica) as entradas:
            for entrada in entradas:
                if entrada.name.startswith('.'):
                    continue
                cuenta += 1
                if cuenta >= tope:
                    return cuenta, True
        return cuenta, False
    except OSError:
        return None, False


# Lo que el visor de vistas previas sabe convertir en imagen.
_CON_MINIATURA = {'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg', 'pdf',
                  'docx', 'xlsx', 'pptx', 'doc', 'xls', 'ppt', 'odt', 'ods', 'odp'}


def contar(usuario_id: int, url: str) -> dict:
    """Todo lo que se puede decir del enlace a quien lo pulsa.

    Nunca lanza: si algo va mal, responde lo que sepa. La tarjeta se dibuja
    igual, solo que con menos detalle.
    """
    senala = leer_enlace(url)
    if not senala:
        return {'es_maquita': es_de_maquita(url), 'acceso': False}

    if senala['clase'] == 'publico':
        return _contar_publico(senala['token'])

    ruta = senala['ruta']
    if not _puede_ver(usuario_id, ruta):
        # Ni siquiera se dice si existe: quien no tiene acceso no ve nada.
        return {'es_maquita': True, 'acceso': False, 'ruta': ruta}

    espacio = _donde_vive(usuario_id, ruta)
    datos = {
        'es_maquita': True,
        'acceso': True,
        'ruta': ruta,
        'nombre': espacio.get('nombre_raiz')
                  or os.path.basename(ruta) or 'Drive Maquita',
        'donde': espacio['donde'],
        'propietario': _nombre_de(espacio['propietario_id'])
    }
    if espacio['propietario_id'] == int(usuario_id):
        datos['propietario'] = 'Tuyo'

    # El trabajo se hace en el espacio del DUEÑO cuando la ruta es de
    # «Compartido conmigo»: el contenido es suyo y ahí está en disco.
    try:
        from permisos_compartidos import resolver
        dueno, ruta_real = resolver(usuario_id, ruta)
    except Exception:
        dueno, ruta_real = usuario_id, ruta

    try:
        fisica = ruta_fisica(dueno, ruta_real)
        estado = os.stat(fisica)
    except (RutaInvalida, OSError):
        datos['existe'] = False
        return datos

    datos['existe'] = True
    datos['modificado'] = int(estado.st_mtime)

    if os.path.isdir(fisica):
        datos['tipo'] = 'carpeta'
        datos['que'] = 'Carpeta del Drive Maquita'
        cuantos, hay_mas = _cuantos_dentro(fisica)
        if cuantos is not None:
            datos['elementos'] = cuantos
            datos['elementos_hay_mas'] = hay_mas
        return datos

    extension = os.path.splitext(fisica)[1].lstrip('.').lower()
    datos['tipo'] = 'archivo'
    datos['extension'] = extension
    datos['que'] = (extension.upper() + ' del Drive Maquita') if extension \
                   else 'Archivo del Drive Maquita'
    datos['peso'] = estado.st_size
    datos['peso_texto'] = peso_legible(estado.st_size)
    if extension in _CON_MINIATURA:
        datos['miniatura'] = ruta        # la pide el navegador a /preview
    return datos


def _contar_publico(token: str) -> dict:
    """Un enlace público («cualquier persona con el enlace»). Se dice de qué
    es y quién lo compartió; el contenido lo protege el propio enlace."""
    datos = {'es_maquita': True, 'acceso': True, 'tipo': 'publico',
             'que': 'Enlace compartido del Drive Maquita'}
    try:
        from almacen_bd import consultar
        filas = consultar(
            'SELECT ruta, propietario_id, expira_en, puede_editar '
            'FROM compartidos WHERE token = %s', (token,))
    except Exception as excepcion:
        log.warning('No se pudo leer el enlace público: %s', excepcion)
        return datos
    if not filas:
        datos['acceso'] = False
        datos['caducado'] = True
        return datos
    fila = filas[0]
    datos['nombre'] = os.path.basename(fila['ruta'] or '') or 'Enlace compartido'
    datos['propietario'] = _nombre_de(fila['propietario_id'])
    datos['donde'] = 'Compartido por enlace'
    if fila['expira_en']:
        datos['expira'] = fila['expira_en'].isoformat()
    return datos
