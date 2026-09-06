# -*- coding: utf-8 -*-
"""
Entrega de los archivos subidos por el chat (imágenes pegadas, adjuntos, audios).

Los dos manejadores de subida guardan en <servicio>/static/uploads/chat/<conversación>/,
fuera de la carpeta estática de Flask; esta ruta los sirve por /uploads/chat/... y
/static/uploads/chat/... (los nginx públicos reenvían ambas formas).

[A-2] Antes esto era una carpeta pública. Ninguna de las dos rutas está en
`_RUTAS_PROTEGIDAS`, así que el `before_request` del servicio no las miraba y
`send_from_directory` entregaba cualquier archivo a quien acertara la ruta, SIN
sesión: los nombres son `<conversación>/<epoch>_<nombre>`, adivinables. Además no
había control de tipo, así que un `.html` subido al chat se servía como página en
el mismo dominio del correo, que es XSS almacenado.

Ahora: hay que tener sesión, hay que ser participante de esa conversación, y solo
las imágenes se muestran incrustadas; todo lo demás se descarga como adjunto.
"""
import os

import psycopg2
from flask import Blueprint, abort, send_from_directory, session

bp_subidos = Blueprint('archivos_subidos', __name__)
_RAIZ = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'static', 'uploads', 'chat'))

# Únicos tipos que se muestran incrustados. SVG queda FUERA a propósito: es XML y
# puede llevar script, así que se descarga como cualquier otro adjunto.
_EXT_INCRUSTABLES = {
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
    '.gif': 'image/gif', '.webp': 'image/webp', '.bmp': 'image/bmp',
    '.mp3': 'audio/mpeg', '.ogg': 'audio/ogg', '.oga': 'audio/ogg',
    '.wav': 'audio/wav', '.webm': 'video/webm', '.mp4': 'video/mp4',
}


def _es_participante(usuario_id, conversacion_id) -> bool:
    """True solo si el usuario participa (y sigue activo) en esa conversación.
    Falla CERRADO: si no se puede comprobar, no se entrega el archivo."""
    try:
        with psycopg2.connect(os.getenv('DATABASE_URL')) as con, con.cursor() as cur:
            cur.execute(
                'SELECT 1 FROM chat_participants '
                'WHERE conversation_id = %s AND user_id = %s AND is_active LIMIT 1',
                (int(conversacion_id), int(usuario_id)))
            return cur.fetchone() is not None
    except Exception:
        return False


def _servir(subruta):
    limpia = subruta.replace('\\', '/')
    partes = [p for p in limpia.split('/') if p]
    if '..' in partes or not partes:
        abort(404)

    usuario_id = session.get('usuario_id')
    if not usuario_id:
        abort(404)   # 404 y no 401: no se confirma que el archivo exista

    # La carpeta es el id de la conversación: solo sus participantes lo ven.
    try:
        conversacion_id = int(partes[0])
    except (TypeError, ValueError):
        abort(404)
    if not _es_participante(usuario_id, conversacion_id):
        abort(404)

    if not os.path.isfile(os.path.join(_RAIZ, limpia)):
        abort(404)

    extension = os.path.splitext(partes[-1])[1].lower()
    tipo = _EXT_INCRUSTABLES.get(extension)
    respuesta = send_from_directory(
        _RAIZ, limpia,
        mimetype=tipo,                    # None -> lo deduce Flask
        as_attachment=tipo is None,       # lo que no es imagen/audio/video: se descarga
        max_age=7 * 24 * 3600,
    )
    # Sin adivinación de tipo: evita que un archivo se interprete como otra cosa.
    respuesta.headers['X-Content-Type-Options'] = 'nosniff'
    # La caché es de este usuario, no de un intermediario compartido.
    respuesta.headers['Cache-Control'] = 'private, max-age=%d' % (7 * 24 * 3600)
    return respuesta


@bp_subidos.route('/uploads/chat/<path:subruta>')
def uploads_chat(subruta):
    return _servir(subruta)


@bp_subidos.route('/static/uploads/chat/<path:subruta>')
def static_uploads_chat(subruta):
    return _servir(subruta)
