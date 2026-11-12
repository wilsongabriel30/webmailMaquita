"""Los enlaces compartidos siguen al documento (14/10/2026).

Las personas esperan que un enlace compartido apunte al DOCUMENTO, no a un nombre
exacto de archivo. Antes, el enlace guardaba la ruta y moría sin aviso si:
  1. se renombraba o movía el archivo (o su carpeta), o
  2. se sustituía el archivo por otro con el mismo nombre en la misma carpeta
     (p. ej. el Word por su PDF, o «Evaluacion» por «Evaluación»).

Este módulo resuelve los dos casos:
  - reubicar(): al mover o renombrar, los enlaces (públicos y entre personas) pasan
    a la ruta nueva, igual que ya hacían los enlaces cortos /a/<código>.
  - reparar_por_token(): al abrir un enlace cuyo archivo ya no está, busca en la
    MISMA carpeta un archivo con el mismo nombre ignorando extensión, tildes,
    mayúsculas y espacios; si lo hay, el enlace pasa a ese archivo y queda anotado
    en la actividad del propietario («enlace_reubicado»).

Nunca lanza excepciones: abrir, mover o renombrar no pueden fallar por esto.
"""

import logging
import os
import unicodedata

from almacen_bd import consultar, ejecutar
from seguridad_rutas import raiz_usuario, ruta_fisica

log = logging.getLogger(__name__)


def _clave_nombre(nombre: str) -> str:
    """Nombre comparable: sin extensión, sin tildes, en minúsculas y sin espacios repetidos."""
    base = os.path.splitext(nombre)[0]
    sin_tildes = ''.join(c for c in unicodedata.normalize('NFKD', base)
                         if not unicodedata.combining(c))
    return ' '.join(sin_tildes.lower().split())


def _ruta_virtual_de(propietario_id, fisica: str):
    """Ruta virtual del propietario para una ruta física de su espacio (o None)."""
    raiz = os.path.realpath(raiz_usuario(propietario_id, 'archivos')).rstrip('/')
    fisica = os.path.realpath(fisica)
    if not fisica.startswith(raiz + '/'):
        return None
    ruta = '/' + os.path.relpath(fisica, raiz)
    try:
        if os.path.realpath(ruta_fisica(propietario_id, ruta)) == fisica:
            return ruta
    except Exception:
        pass
    return None


def _anotar(propietario_id, ruta, detalle):
    try:
        ejecutar('INSERT INTO actividad (usuario_id, accion, ruta, detalle) '
                 'VALUES (%s, %s, %s, %s)',
                 (propietario_id, 'enlace_reubicado', ruta, detalle[:300]))
    except Exception as excepcion:
        log.warning('enlaces: no se pudo anotar la reubicación (%s)', excepcion)


def reubicar(origen_fisico, destino_fisico):
    """Tras mover o renombrar: los enlaces del archivo (o de lo que haya dentro de
    la carpeta) pasan a la ruta nueva."""
    try:
        origen = os.path.realpath(origen_fisico).rstrip('/')
        destino = os.path.realpath(destino_fisico).rstrip('/')
        for fila in consultar('SELECT id, propietario_id, ruta FROM compartidos'):
            try:
                actual = os.path.realpath(ruta_fisica(fila['propietario_id'], fila['ruta']))
            except Exception:
                continue
            if actual != origen and not actual.startswith(origen + '/'):
                continue
            nueva = _ruta_virtual_de(fila['propietario_id'], destino + actual[len(origen):])
            if not nueva:
                log.warning('enlaces: %s salió del espacio del propietario; enlace %s sin reubicar',
                            destino, fila['id'])
                continue
            ejecutar('UPDATE compartidos SET ruta = %s WHERE id = %s', (nueva, fila['id']))
    except Exception as excepcion:
        log.warning('enlaces: no se pudo reubicar %s → %s (%s)',
                    origen_fisico, destino_fisico, excepcion)


def _reemplazo(fisica: str):
    """Archivo de la misma carpeta con el mismo nombre (ignorando extensión, tildes,
    mayúsculas y espacios). Si hay varios, el modificado más recientemente."""
    carpeta = os.path.dirname(fisica)
    if not os.path.isdir(carpeta):
        return None
    clave = _clave_nombre(os.path.basename(fisica))
    candidatos = []
    for nombre in os.listdir(carpeta):
        completo = os.path.join(carpeta, nombre)
        if os.path.isfile(completo) and _clave_nombre(nombre) == clave:
            candidatos.append((os.path.getmtime(completo), completo))
    return max(candidatos)[1] if candidatos else None


def reparar_fila(fila) -> bool:
    """Si el archivo del enlace ya no existe y hay un reemplazo, reubica el enlace."""
    try:
        fisica = ruta_fisica(fila['propietario_id'], fila['ruta'])
        if os.path.exists(fisica):
            return False
        nuevo = _reemplazo(fisica)
        if not nuevo:
            return False
        nueva = _ruta_virtual_de(fila['propietario_id'], nuevo)
        if not nueva:
            return False
        ejecutar('UPDATE compartidos SET ruta = %s WHERE id = %s', (nueva, fila['id']))
        _anotar(fila['propietario_id'], nueva,
                'El enlace pasó de «%s» (ya no existe) a este archivo' % fila['ruta'].rsplit('/', 1)[-1])
        log.info('enlaces: enlace %s reubicado de %s a %s', fila['id'], fila['ruta'], nueva)
        return True
    except Exception as excepcion:
        log.warning('enlaces: no se pudo reparar el enlace %s (%s)', fila.get('id'), excepcion)
        return False


def reparar_por_token(token) -> None:
    """Gancho para los puntos que abren un enlace por su token. Nunca lanza."""
    try:
        if not token:
            return
        filas = consultar('SELECT id, propietario_id, ruta FROM compartidos WHERE token = %s',
                          (token,))
        if filas:
            reparar_fila(dict(filas[0]))
    except Exception as excepcion:
        log.warning('enlaces: reparación por token fallida (%s)', excepcion)


def reparar_todos() -> int:
    """Revisa todos los enlaces (uso manual o programado). Devuelve cuántos reubicó."""
    reubicados = 0
    for fila in consultar('SELECT id, propietario_id, ruta FROM compartidos'):
        if reparar_fila(dict(fila)):
            reubicados += 1
    return reubicados
