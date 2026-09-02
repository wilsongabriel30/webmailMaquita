# -*- coding: utf-8 -*-
"""
Carpetas del sistema en el Drive (T-18 y T-22): «Archivos del chat» y «Archivos del correo».
- «Archivos del chat»: la carpeta raíz no se borra, mueve ni renombra (su contenido sí).
- «Archivos del correo»: la administra el correo; nada dentro se borra, mueve ni renombra desde el Drive.
  Al intentarlo se responde 403 `pertenece_al_correo` con los datos del correo dueño y su enlace, para que la
  interfaz lleve al usuario al correo (allí se elimina, de forma irreversible, el correo con sus adjuntos).
"""
import logging

from flask import jsonify

log = logging.getLogger('almacen.protecciones')
CARPETA_CHAT = '/Archivos del chat'
CARPETAS_SISTEMA = ('/Archivos del chat', '/Grabaciones de reuniones')   # raíz intocable; su contenido sí
CARPETA_CORREO = '/Archivos del correo'
URL_WEBMAIL = 'https://mail.maquita.org/webmail/'


def _norm(ruta) -> str:
    return '/' + str(ruta or '').strip().strip('/')


def es_carpeta_chat(ruta) -> bool:
    """Carpeta raíz del sistema («Archivos del chat», «Grabaciones de reuniones»): no se borra, mueve ni renombra."""
    return _norm(ruta).lower() in {c.lower() for c in CARPETAS_SISTEMA}


def es_de_correo(ruta) -> bool:
    r = _norm(ruta).lower()
    return r == CARPETA_CORREO.lower() or r.startswith(CARPETA_CORREO.lower() + '/')


def datos_correo(usuario_id, ruta):
    """Correo dueño del adjunto (o None)."""
    try:
        from almacen_bd import consultar
        filas = consultar("""SELECT buzon, carpeta_correo, uid, asunto, remitente, fecha_correo FROM correo_adjuntos
                             WHERE usuario_id = %s AND ruta_drive = %s AND estado = 'activo' ORDER BY id DESC LIMIT 1""",
                          (int(usuario_id), _norm(ruta)))
    except Exception as exc:
        log.warning('sin datos del correo para %s: %s', ruta, exc)
        return None
    if not filas:
        return None
    f = filas[0]
    return {'buzon': f['buzon'], 'carpeta': f['carpeta_correo'], 'uid': f['uid'], 'asunto': f['asunto'],
            'remitente': f['remitente'], 'fecha': str(f['fecha_correo'] or ''),
            'url': f"{URL_WEBMAIL}?folder={f['carpeta_correo']}&uid={f['uid']}"}


def error_pertenece_al_correo(usuario_id, ruta):
    resp = jsonify({'success': False, 'error': 'pertenece_al_correo',
                    'mensaje': 'Este archivo pertenece a un correo. Para eliminarlo, abre el correo y elimínalo desde allí '
                               '(esa acción no es reversible: el correo y sus adjuntos se eliminarán permanentemente).',
                    'correo': datos_correo(usuario_id, ruta)})
    return resp, 403


def error_carpeta_chat(accion):
    return jsonify({'success': False,
                    'error': f'Esa carpeta es del sistema (Archivos del chat / Grabaciones de reuniones) y no se puede {accion}; su contenido sí'}), 403


def error_carpeta_correo(accion):
    return jsonify({'success': False,
                    'error': f'«Archivos del correo» la administra el correo: no se puede {accion} nada hacia o desde esa carpeta'}), 403
