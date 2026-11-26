# -*- coding: utf-8 -*-
"""
Servicio interno del Almacén para IA Maquita: SOLO LECTURA (04/11/2026).
=======================================================================
IA Maquita (servidor propio) usa los documentos de la persona que
tiene la sesión en el chat para responder sobre ellos. Antes los leía de
Nextcloud, que ya no existe; ahora los pide aquí.

Qué entrega y qué no:
  · Solo el espacio PROPIO de la persona («Mi unidad»: <raíz>/<id>/archivos).
    Nada de unidades compartidas, nada de «Compartido conmigo», nada de otros
    usuarios y ningún privilegio de master.
  · Respeta la papelera: lo que está en ella ya no vive en «archivos», así que
    no aparece ni se puede descargar.
  · Solo PDF, DOCX, XLSX, ODT, TXT, MD y CSV de hasta 20 MB.
  · No escribe nada: no hay subidas, ni borrados, ni cambios de permisos.

Quién puede llamar (las tres cosas a la vez; si falta una, falla cerrado):
  1. Token de servicio propio `ALMACEN_SERVICIO_IA_TOKEN` (cabecera
     `Authorization: Bearer …`), leído del .env del Almacén, nunca del código.
     Si falta o mide menos de 32 caracteres, el servicio responde 503.
  2. IP de origen en `ALMACEN_SERVICIO_IA_IPS` (hoy una sola). Se usa
     la IP que vio nginx y se exige que la cadena de reenvío tenga un solo
     elemento: una cabecera inventada no sirve.
  3. El `usuario_id` lo decide IA Maquita a partir de la sesión del chat (que
     nace del token SSO firmado por Raíces), nunca el navegador.

Cada llamada queda en el registro de faro-maquita con la marca SERVICIO_IA.

Autoría: Equipo de Tecnología Maquita — 2026-11-04
"""
import hmac
import logging
import os
import stat
import time
from datetime import datetime, timezone

from flask import Blueprint, Response, jsonify, request

from almacen_bd import consultar
from archivos_internos import es_nombre_interno
from config_almacen import raiz_datos
from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual

log = logging.getLogger('almacen.servicio_ia')
log.setLevel(logging.INFO)          # la auditoría (op=… resultado=ok) debe quedar escrita

PREFIJO = '/api/almacen/servicio-ia'
bp_servicio_ia = Blueprint('almacen_servicio_ia', __name__)

ENV_ALMACEN = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
EXTENSIONES = ('pdf', 'docx', 'xlsx', 'odt', 'txt', 'md', 'csv')
TAMANO_MAXIMO = 20 * 1024 * 1024
MAXIMO_ARCHIVOS = 2000

# Carpetas de programas y dependencias: no son documentos y solo meten ruido.
_CARPETAS_EXCLUIDAS = {'venv', '.venv', 'node_modules', 'site-packages', '__pycache__',
                       '.git', '.svn', '.cache', '.tox', '.idea', '.vscode'}

_entorno_cache = {'leido_en': 0.0, 'valores': {}}


def _entorno(clave: str) -> str:
    """Lee una clave del .env del Almacén (se relee cada 60 s: rotar el token
    no exige recargar Raíces)."""
    ahora = time.time()
    if ahora - _entorno_cache['leido_en'] > 60:
        valores = {}
        try:
            with open(ENV_ALMACEN, encoding='utf-8') as fichero:
                for linea in fichero:
                    linea = linea.strip()
                    if linea and not linea.startswith('#') and '=' in linea:
                        k, v = linea.split('=', 1)
                        valores[k.strip()] = v.strip().strip('"').strip("'")
        except OSError as exc:
            log.error('SERVICIO_IA no se pudo leer %s: %s', ENV_ALMACEN, exc)
        _entorno_cache.update(leido_en=ahora, valores=valores)
    return _entorno_cache['valores'].get(clave, '')


def _en_hilo_nativo(funcion, *args):
    """Trabajo de disco (NFS) fuera del bucle de eventlet, igual que api_archivos."""
    try:
        from eventlet import patcher as _patcher, tpool as _tpool
        if _patcher.is_monkey_patched('socket'):
            return _tpool.execute(funcion, *args)
    except ImportError:
        pass
    return funcion(*args)


def _ip_origen() -> str:
    return (request.remote_addr or '').strip()


def _ip_permitida() -> bool:
    """IP de la conexión que vio nginx, sin cabeceras de reenvío del cliente."""
    permitidas = {ip.strip() for ip in _entorno('ALMACEN_SERVICIO_IA_IPS').split(',') if ip.strip()}
    ip = _ip_origen()
    cadena = [x.strip() for x in request.headers.get('X-Forwarded-For', '').split(',') if x.strip()]
    real = request.headers.get('X-Real-IP', '').strip()
    return bool(ip) and ip in permitidas and cadena == [ip] and real == ip


def _rechazo():
    """Devuelve la respuesta de rechazo o None si la llamada está autorizada."""
    esperado = _entorno('ALMACEN_SERVICIO_IA_TOKEN')
    if len(esperado) < 32:
        log.error('SERVICIO_IA_SIN_CONFIGURAR ip=%s', _ip_origen())
        return jsonify({'success': False, 'error': 'Servicio no disponible'}), 503
    if not _ip_permitida():
        log.warning('SERVICIO_IA_IP_RECHAZADA ip=%s xff=%s ruta=%s', _ip_origen(),
                    request.headers.get('X-Forwarded-For', ''), request.path)
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    cabecera = request.headers.get('Authorization', '')
    recibido = cabecera[7:].strip() if cabecera.startswith('Bearer ') else ''
    if not recibido or not hmac.compare_digest(recibido.encode(), esperado.encode()):
        log.warning('SERVICIO_IA_TOKEN_RECHAZADO ip=%s ruta=%s', _ip_origen(), request.path)
        return jsonify({'success': False, 'error': 'No autorizado'}), 403
    return None


def _usuario_pedido():
    """usuario_id de la consulta: entero positivo y usuario activo en Raíces."""
    try:
        usuario_id = int(request.args.get('usuario_id', ''))
    except (TypeError, ValueError):
        return None
    if usuario_id <= 0:
        return None
    filas = consultar('SELECT active FROM usuarios WHERE id = %s', (usuario_id,), nomina=True)
    if not filas or not filas[0]['active']:
        return None
    return usuario_id


def _base_propia(usuario_id: int):
    """Carpeta física de «Mi unidad» (realpath) o None si aún no existe.
    No se usa raiz_usuario() porque esta crea la carpeta, y aquí solo se lee."""
    base = os.path.realpath(os.path.join(raiz_datos(), str(int(usuario_id)), 'archivos'))
    return base if os.path.isdir(base) else None


def _fisica_segura(base: str, ruta: str):
    """Ruta física de un documento PROPIO o None. Rechaza espacios ajenos,
    carpetas internas, extensiones no admitidas y cualquier enlace simbólico."""
    try:
        ruta = normalizar_ruta_virtual(ruta)
    except RutaInvalida:
        return None
    partes = [p for p in ruta.split('/') if p]
    if not partes or partes[0] in ('unidades', 'compartido'):
        return None
    if any(es_nombre_interno(p) or p.lower() in _CARPETAS_EXCLUIDAS for p in partes):
        return None
    if os.path.splitext(partes[-1])[1].lower().lstrip('.') not in EXTENSIONES:
        return None
    destino = os.path.normpath(os.path.join(base, *partes))
    # realpath igual a la ruta normalizada = no hay enlaces simbólicos en el camino
    if os.path.realpath(destino) != destino or not destino.startswith(base + os.sep):
        return None
    return destino


def _ficha(base: str, ruta: str):
    """Datos de un documento verificados EN DISCO (el índice es solo un espejo)."""
    fisica = _fisica_segura(base, ruta)
    if not fisica:
        return None
    try:
        info = os.lstat(fisica)
    except OSError:
        return None                       # ya no existe: borrado o en la papelera
    if not stat.S_ISREG(info.st_mode) or info.st_size > TAMANO_MAXIMO or info.st_size == 0:
        return None
    return {
        'ruta': normalizar_ruta_virtual(ruta),
        'nombre': os.path.basename(fisica),
        'tamano': info.st_size,
        'modificado': datetime.fromtimestamp(info.st_mtime, tz=timezone.utc).isoformat(),
        'huella': '%d-%d' % (info.st_size, int(info.st_mtime)),
    }


def _listar_en_disco(base: str, rutas: list) -> list:
    fichas = []
    for ruta in rutas:
        ficha = _ficha(base, ruta)
        if ficha:
            fichas.append(ficha)
    return fichas


@bp_servicio_ia.route('/archivos', methods=['GET'])
def listar_documentos():
    """Documentos propios de la persona, con su huella (tamaño-fecha)."""
    rechazo = _rechazo()
    if rechazo:
        return rechazo
    usuario_id = _usuario_pedido()
    if not usuario_id:
        log.info('SERVICIO_IA op=listar usuario=%s ip=%s resultado=usuario_no_valido',
                 request.args.get('usuario_id', ''), _ip_origen())
        return jsonify({'success': False, 'error': 'Usuario no válido'}), 404
    try:
        base = _base_propia(usuario_id)
        if not base:
            return jsonify({'success': True, 'archivos': [], 'total': 0})
        filas = consultar(
            """SELECT ruta FROM indice_nombres
                WHERE usuario_id = %s AND NOT es_carpeta
                  AND lower(extension) = ANY(%s) AND tamano <= %s
                  AND ruta NOT LIKE '/unidades/%%' AND ruta NOT LIKE '/compartido/%%'
                ORDER BY modificado_en DESC NULLS LAST
                LIMIT %s""",
            (usuario_id, list(EXTENSIONES), TAMANO_MAXIMO, MAXIMO_ARCHIVOS))
        fichas = _en_hilo_nativo(_listar_en_disco, base, [f['ruta'] for f in filas])
    except Exception as exc:
        log.error('SERVICIO_IA op=listar usuario=%s ip=%s resultado=error %s',
                  usuario_id, _ip_origen(), exc)
        return jsonify({'success': False, 'error': 'No se pudo listar'}), 503
    log.info('SERVICIO_IA op=listar usuario=%s ip=%s resultado=ok archivos=%d',
             usuario_id, _ip_origen(), len(fichas))
    return jsonify({'success': True, 'archivos': fichas, 'total': len(fichas)})


def _leer(fisica: str) -> bytes:
    with open(fisica, 'rb') as fichero:
        return fichero.read(TAMANO_MAXIMO + 1)


@bp_servicio_ia.route('/archivo', methods=['GET'])
def descargar_documento():
    """Contenido de UN documento propio (para extraer su texto)."""
    rechazo = _rechazo()
    if rechazo:
        return rechazo
    usuario_id = _usuario_pedido()
    ruta = request.args.get('ruta', '')
    if not usuario_id:
        return jsonify({'success': False, 'error': 'Usuario no válido'}), 404
    try:
        base = _base_propia(usuario_id)
        ficha = _en_hilo_nativo(_ficha, base, ruta) if base else None
        if not ficha:
            log.info('SERVICIO_IA op=descargar usuario=%s ip=%s resultado=no_disponible',
                     usuario_id, _ip_origen())
            return jsonify({'success': False, 'error': 'No disponible'}), 404
        contenido = _en_hilo_nativo(_leer, _fisica_segura(base, ruta))
    except Exception as exc:
        log.error('SERVICIO_IA op=descargar usuario=%s ip=%s resultado=error %s',
                  usuario_id, _ip_origen(), exc)
        return jsonify({'success': False, 'error': 'No se pudo leer'}), 503
    if len(contenido) > TAMANO_MAXIMO:
        return jsonify({'success': False, 'error': 'Demasiado grande'}), 413
    log.info('SERVICIO_IA op=descargar usuario=%s ip=%s resultado=ok bytes=%d',
             usuario_id, _ip_origen(), len(contenido))
    respuesta = Response(contenido, mimetype='application/octet-stream')
    respuesta.headers['X-Huella'] = ficha['huella']
    respuesta.headers['Cache-Control'] = 'no-store'
    return respuesta


def registrar(app) -> None:
    """Monta el servicio bajo /api/almacen/servicio-ia (lo llama integracion_faro)."""
    app.register_blueprint(bp_servicio_ia, url_prefix=PREFIJO)
