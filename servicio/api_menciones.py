"""Menciones en comentarios — Drive Maquita.

Cuando alguien escribe «@Nombre» en un comentario del editor, OnlyOffice lanza
el evento `onRequestSendNotify`. Sin nadie escuchándolo, la mención se escribe
y AHÍ SE QUEDA: la persona mencionada no se entera hasta que abre el archivo
por casualidad. En Google Drive te llega el aviso al instante, y eso es lo que
hace que mencionar sirva de algo.

Este módulo cierra ese hueco: convierte la mención en una notificación de FARO
(la campanita), con un enlace que lleva al comentario exacto.

Backend de la lista de personas: `api_oo_drive.oo_usuarios` (/onlyoffice/usuarios)
Doc: 00-CLAUDE-CONTEXTO/EDICION-REFERENCIAS-Y-MACROS-ONLYOFFICE.md
"""

import logging
import sys
from urllib.parse import quote

from flask import Blueprint, jsonify, request

from almacen_bd import consultar
from api_archivos import error, usuario_actual
from config_almacen import URL_LINKS
from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual

log = logging.getLogger('almacen.menciones')

bp_menciones = Blueprint('almacen_menciones', __name__)

# Tope por mención. Nadie etiqueta a 40 personas en un comentario legítimo, y
# sin límite esto sería una forma cómoda de inundar la campanita de todos.
MAXIMO_DESTINATARIOS = 20


def _crear_notificacion(*args, **kwargs):
    """Notificador de FARO, importado de forma perezosa.

    Se importa aquí y no arriba porque el Almacén también se ejecuta suelto
    (app_almacen.py), fuera de FARO, y en ese caso el módulo no existe. Si no
    se puede importar, la mención sigue guardándose en el documento: se pierde
    el aviso, no el comentario.
    """
    try:
        if '/home/sistemas/Maquita' not in sys.path:
            sys.path.insert(0, '/home/sistemas/Maquita')
        from modulos.nomina.servicios_legacy.notificaciones_app import (
            crear_notificacion_usuario)
        return crear_notificacion_usuario(*args, **kwargs)
    except Exception as excepcion:
        log.warning('No se pudo notificar la mención: %s', excepcion)
        return False


@bp_menciones.route('/onlyoffice/mencion', methods=['POST'])
def mencion():
    """POST /onlyoffice/mencion — {ruta, emails[], mensaje, enlace}

    Lo llama `onRequestSendNotify` desde el editor. Avisa por la campanita de
    FARO a cada persona mencionada.
    """
    quien_menciona = usuario_actual()
    datos = request.get_json() or {}

    try:
        ruta = normalizar_ruta_virtual(datos.get('ruta', ''))
    except RutaInvalida as excepcion:
        return error(str(excepcion), 400)

    correos = [c.strip().lower() for c in (datos.get('emails') or [])
               if isinstance(c, str) and c.strip()]
    if not correos:
        return jsonify({'success': True, 'avisados': 0})
    correos = correos[:MAXIMO_DESTINATARIOS]

    nombre_archivo = ruta.rsplit('/', 1)[-1]
    comentario = (datos.get('mensaje') or '').strip()[:400]

    # El enlace lleva AL COMENTARIO, no solo al archivo: OnlyOffice manda un
    # `actionLink` que el editor entiende y usa para posicionarse. Se arma
    # sobre URL_LINKS (siempre drive.maquita.com.ec) porque la notificación
    # puede abrirse desde cualquier sitio, incluido el correo.
    destino = '%s/archivos-almacen/editar?ruta=%s' % (URL_LINKS, quote(ruta))
    enlace_accion = datos.get('enlace')
    if enlace_accion:
        destino += '&enlace=' + quote(str(enlace_accion))

    filas = consultar(
        "SELECT id, COALESCE(email, '') AS email FROM usuarios "
        "WHERE active = TRUE AND LOWER(email) = ANY(%s)",
        (correos,), nomina=True)

    quien = _nombre_de(quien_menciona)
    avisados = 0
    for fila in filas:
        if _crear_notificacion(
                fila['id'],
                'mencion_documento',
                '%s te mencionó en %s' % (quien, nombre_archivo),
                comentario or 'Te mencionaron en un comentario.',
                action_url=destino,
                reference_type='almacen_documento',
                reference_id=None):
            avisados += 1

    log.info('Mención en %s por %s: %s avisados de %s correos',
             ruta, quien_menciona, avisados, len(correos))
    return jsonify({'success': True, 'avisados': avisados})


def _nombre_de(usuario):
    """Nombre legible de quien menciona; si no se encuentra, su usuario."""
    try:
        filas = consultar(
            "SELECT COALESCE(t.nombres || ' ' || t.apellidos, u.full_name, "
            "       u.username) AS nombre "
            "FROM usuarios u LEFT JOIN trabajadores t ON u.trabajador_id = t.id "
            "WHERE u.username = %s OR u.id::text = %s LIMIT 1",
            (str(usuario), str(usuario)), nomina=True)
        if filas:
            return filas[0]['nombre']
    except Exception:
        pass
    return str(usuario)
