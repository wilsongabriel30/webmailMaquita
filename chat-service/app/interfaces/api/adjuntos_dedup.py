# -*- coding: utf-8 -*-
"""
Adjuntos del chat sin duplicados (T-32): una copia física, N referencias.
- Cada archivo subido se registra con su huella SHA-256 en `chat_adjuntos_huellas` (usuario, conversación, ruta, nombre).
- Si ya existe en disco un archivo con la misma huella, el recién guardado se sustituye por un ENLACE DURO a la copia
  existente (mismo inodo, 0 bytes nuevos). El mensaje se ve normal; por debajo apuntan a la misma copia.
- GET  /api/chat/adjuntos/existe?sha256=…                      → si ESTE usuario ya envió ese contenido: cuándo y a quién.
- POST /api/chat/conversations/<cid>/messages/adjuntar-existente {sha256, nombre, message_type}
                                                                 → envía el archivo existente como mensaje nuevo (sin subir).
- La copia física solo desaparece cuando cae la última referencia (nadie borra archivos aquí: la limpieza es un
  trabajo aparte que cuenta referencias en chat_message_media + chat_adjuntos_huellas).
"""
import hashlib
import os
from datetime import datetime

import psycopg2
import psycopg2.extras
from flask import Blueprint, jsonify, request, session
from werkzeug.utils import secure_filename

bp_adjuntos_dedup = Blueprint('adjuntos_dedup', __name__, url_prefix='/api/chat')
RAIZ = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))


def _con():
    return psycopg2.connect(os.environ['DATABASE_URL'])


def asegurar_tabla():
    with _con() as con, con.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS chat_adjuntos_huellas (
                           id SERIAL PRIMARY KEY, sha256 CHAR(64) NOT NULL, usuario_id INTEGER NOT NULL,
                           conversation_id INTEGER, ruta TEXT NOT NULL, nombre VARCHAR(255), bytes BIGINT NOT NULL DEFAULT 0,
                           creado_en TIMESTAMP NOT NULL DEFAULT NOW());
                       CREATE INDEX IF NOT EXISTS ix_cah_usuario_sha ON chat_adjuntos_huellas (usuario_id, sha256);
                       CREATE INDEX IF NOT EXISTS ix_cah_sha ON chat_adjuntos_huellas (sha256)""")


def huella(ruta, bloque=1 << 20):
    h = hashlib.sha256()
    with open(ruta, 'rb') as f:
        for trozo in iter(lambda: f.read(bloque), b''):
            h.update(trozo)
    return h.hexdigest()


def _abs(ruta):
    return ruta if os.path.isabs(ruta) else os.path.join(RAIZ, ruta)


def _rel(ruta):
    ruta = os.path.abspath(ruta)
    return os.path.relpath(ruta, RAIZ).replace('\\', '/') if ruta.startswith(RAIZ) else ruta


def _copia_existente(sha, distinta_de):
    """Ruta absoluta de otra copia física con la misma huella que exista en disco (o None)."""
    with _con() as con, con.cursor() as cur:
        cur.execute("SELECT ruta FROM chat_adjuntos_huellas WHERE sha256 = %s ORDER BY id LIMIT 20", (sha,))
        for (r,) in cur.fetchall():
            a = _abs(r)
            if os.path.isfile(a) and not os.path.samefile(a, distinta_de):
                return a
    return None


def registrar_archivos(conversacion_id, usuario_id, lista):
    """lista: [(ruta_guardada, nombre_original)]. Calcula la huella, deduplica físicamente y registra. Nunca lanza."""
    for ruta, nombre in lista or []:
        try:
            a = _abs(ruta)
            if not os.path.isfile(a):
                continue
            sha = huella(a)
            existente = _copia_existente(sha, a)
            if existente:
                try:
                    tmp = a + '.dedup'
                    os.link(existente, tmp)
                    os.replace(tmp, a)       # el archivo recién subido pasa a ser un enlace duro a la copia existente
                except OSError as e:
                    print(f'[adjuntos-dedup] sin enlace duro ({e}); se conserva la copia')
            with _con() as con, con.cursor() as cur:
                cur.execute("INSERT INTO chat_adjuntos_huellas (sha256, usuario_id, conversation_id, ruta, nombre, bytes) VALUES (%s,%s,%s,%s,%s,%s)",
                            (sha, int(usuario_id), conversacion_id, _rel(a), (nombre or os.path.basename(a))[:255], os.path.getsize(a)))
        except Exception as e:
            print(f'[adjuntos-dedup] {ruta}: {e}')


@bp_adjuntos_dedup.route('/adjuntos/existe', methods=['GET'])
def existe():
    uid = session.get('usuario_id')
    if not uid:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    sha = (request.args.get('sha256') or '').strip().lower()
    if len(sha) != 64:
        return jsonify({'success': False, 'error': 'sha256 inválido'}), 400
    with _con() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("""SELECT h.id, h.ruta, h.nombre, h.bytes, h.creado_en, h.conversation_id,
                              c.conversation_type, c.name,
                              (SELECT COALESCE(NULLIF(TRIM(u.full_name), ''), u.username) FROM chat_participants p JOIN usuarios u ON u.id = p.user_id
                               WHERE p.conversation_id = h.conversation_id AND p.user_id <> h.usuario_id AND c.conversation_type = 'direct' LIMIT 1) AS otro
                       FROM chat_adjuntos_huellas h LEFT JOIN chat_conversations c ON c.id = h.conversation_id
                       WHERE h.usuario_id = %s AND h.sha256 = %s ORDER BY h.id DESC LIMIT 10""", (int(uid), sha))
        filas = [f for f in cur.fetchall() if os.path.isfile(_abs(f['ruta']))]
    if not filas:
        return jsonify({'success': True, 'existe': False})
    f = filas[0]
    destino = f['otro'] or f['name'] or ('Mis notas' if f['conversation_type'] == 'group' else 'una conversación')
    return jsonify({'success': True, 'existe': True, 'nombre': f['nombre'], 'bytes': f['bytes'], 'fecha': f['creado_en'].isoformat(timespec='minutes'),
                    'destinatario': destino, 'veces': len(filas)})


@bp_adjuntos_dedup.route('/conversations/<int:cid>/messages/adjuntar-existente', methods=['POST'])
def adjuntar_existente(cid):
    uid = session.get('usuario_id')
    if not uid:
        return jsonify({'success': False, 'error': 'No autenticado'}), 401
    d = request.get_json(silent=True) or {}
    sha = (d.get('sha256') or '').strip().lower()
    if len(sha) != 64:
        return jsonify({'success': False, 'error': 'sha256 inválido'}), 400
    with _con() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("SELECT ruta, nombre, bytes FROM chat_adjuntos_huellas WHERE usuario_id = %s AND sha256 = %s ORDER BY id DESC LIMIT 20", (int(uid), sha))
        origen = next((f for f in cur.fetchall() if os.path.isfile(_abs(f['ruta']))), None)
    if not origen:
        return jsonify({'success': False, 'error': 'No tienes ese archivo enviado antes'}), 404
    nombre = (d.get('nombre') or origen['nombre'] or 'archivo')
    tipo = d.get('message_type') or d.get('tipo') or 'document'
    if tipo not in ('image', 'video', 'audio', 'document', 'gif'):
        tipo = 'document'
    destino_dir = os.path.join(RAIZ, 'static', 'uploads', 'chat', str(cid))
    os.makedirs(destino_dir, exist_ok=True)
    destino = os.path.join(destino_dir, datetime.now().strftime('%Y%m%d_%H%M%S%f_') + secure_filename(nombre))
    try:
        os.link(_abs(origen['ruta']), destino)      # misma copia física, referencia nueva
    except OSError:
        import shutil
        shutil.copy2(_abs(origen['ruta']), destino)
    import mimetypes
    mime = mimetypes.guess_type(nombre)[0] or 'application/octet-stream'
    archivos_data = [{'ruta': _rel(destino), 'nombre': nombre, 'tamanio': os.path.getsize(destino), 'tipo_mime': mime}]
    from interfaces.api.controlador_chat import obtener_servicio_chat
    from interfaces.websocket import emitir_mensaje_nuevo
    servicio = obtener_servicio_chat()
    res = servicio.enviar_mensaje_con_archivos(conversacion_id=cid, remitente_id=int(uid), archivos=archivos_data, tipo_media=tipo,
                                              contenido=(d.get('content') or '').strip() or None)
    if not res.exito:
        return jsonify({'success': False, 'error': res.mensaje}), 400
    registrar_archivos(cid, uid, [(destino, nombre)])
    try:
        from interfaces.api.drive_chat import reflejar_en_drive
        reflejar_en_drive(cid, int(uid), [(destino, nombre)])
    except Exception as e:
        print(f'[adjuntos-dedup] drive: {e}')
    msg = (res.datos or {}).get('mensaje') or {}
    message = {'id': msg.get('id'), 'content': msg.get('contenido'), 'message_type': tipo, 'sender_id': int(uid), 'created_at': msg.get('creado_en'),
               'is_own_message': True, 'media': [{'file_path': a.get('ruta'), 'media_type': tipo, 'file_name': a.get('nombre'), 'file_size': a.get('tamanio')} for a in msg.get('archivos', [])]}
    try:
        md = dict(msg); md['remitente'] = {'id': int(uid), 'nombre': session.get('usuario_nombre', 'Usuario')}
        emitir_mensaje_nuevo(cid, md)
    except Exception as e:
        print(f'[adjuntos-dedup] emitir: {e}')
    return jsonify({'success': True, 'exito': True, 'message': message, 'reutilizado': True})
