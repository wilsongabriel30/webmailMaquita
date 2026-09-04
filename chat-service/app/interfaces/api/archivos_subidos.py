# -*- coding: utf-8 -*-
"""
Entrega de los archivos subidos por el chat (imágenes pegadas, adjuntos, audios).
Los dos manejadores de subida guardan en <servicio>/static/uploads/chat/<conversación>/, fuera de la carpeta
estática de Flask; esta ruta los sirve por /uploads/chat/... y /static/uploads/chat/... (los nginx públicos
reenvían ambas formas). Sin listado de directorios; solo archivos existentes.
"""
import os

from flask import Blueprint, abort, send_from_directory

bp_subidos = Blueprint('archivos_subidos', __name__)
_RAIZ = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'static', 'uploads', 'chat'))


def _servir(subruta):
    if '..' in subruta.replace('\\', '/').split('/'):
        abort(404)
    if not os.path.isfile(os.path.join(_RAIZ, subruta)):
        abort(404)
    return send_from_directory(_RAIZ, subruta, max_age=7 * 24 * 3600)


@bp_subidos.route('/uploads/chat/<path:subruta>')
def uploads_chat(subruta):
    return _servir(subruta)


@bp_subidos.route('/static/uploads/chat/<path:subruta>')
def static_uploads_chat(subruta):
    return _servir(subruta)
