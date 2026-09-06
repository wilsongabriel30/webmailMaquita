# -*- coding: utf-8 -*-
"""
T-46 · Apoyo para la sección «Llamadas»: favoritos y frecuentes.

  GET    /api/chat/llamadas/frecuentes        → con quién hablas más (últimos 90 días)
  GET    /api/chat/llamadas/favoritos         → tus favoritos
  POST   /api/chat/llamadas/favoritos         {usuario_id}   → marcar
  DELETE /api/chat/llamadas/favoritos/<id>                   → quitar

El buscador de personas y el historial ya existían (`/api/chat/users/search` y
`/api/chat/llamadas/historial`): esta pieza solo añade lo que faltaba.

Autor: Wilson Arguello
"""
from interfaces.api.chat_base import *  # noqa: F401,F403  (bp_chat, request, jsonify, autenticación…)
from sqlalchemy import text
from flask import session

DDL = """
CREATE TABLE IF NOT EXISTS chat_llamadas_favoritos (
    usuario_id  INTEGER NOT NULL,
    contacto_id INTEGER NOT NULL,
    creado_en   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (usuario_id, contacto_id)
)
"""

SQL_PERSONA = """
SELECT u.id, COALESCE(NULLIF(u.full_name, ''), u.username) AS nombre,
       COALESCE(NULLIF(t.foto_perfil, ''), NULLIF(u.profile_picture, ''), '') AS foto,
       COALESCE(c.nombre, '') AS cargo
FROM usuarios u
LEFT JOIN trabajadores t ON t.id = u.trabajador_id
LEFT JOIN cargos c ON c.id = t.cargo_id
WHERE u.id = ANY(:ids)
"""


def _sesion():
    return obtener_gestor().session()


def asegurar_tabla():
    try:
        s = _sesion()
        s.execute(text(DDL)); s.commit(); s.close()
    except Exception:
        pass


def _foto(v):
    if not v:
        return ''
    if v.startswith('http') or v.startswith('/'):
        return v
    if v.startswith('uploads/'):
        return 'https://datos.maquita.com.ec/static/' + v
    return 'https://datos.maquita.com.ec/static/uploads/profiles/' + v


def _personas(s, ids):
    if not ids:
        return {}
    filas = s.execute(text(SQL_PERSONA), {'ids': list(ids)}).fetchall()
    return {f[0]: {'id': f[0], 'nombre': f[1], 'foto': _foto(f[2]), 'cargo': f[3]} for f in filas}


@bp_chat.route('/llamadas/frecuentes', methods=['GET'])
@requiere_autenticacion
def llamadas_frecuentes():
    """Con quién hablas más por llamada (para la marcación rápida)."""
    uid = session.get('usuario_id')
    s = _sesion()
    try:
        filas = s.execute(text("""
            SELECT CASE WHEN caller_id = :u THEN callee_id ELSE caller_id END AS otro, count(*) AS veces
            FROM chat_llamadas
            WHERE (caller_id = :u OR callee_id = :u) AND creado_en > NOW() - INTERVAL '90 days'
              AND COALESCE(tipo, '') <> 'conferencia'
            GROUP BY 1 HAVING CASE WHEN caller_id = :u THEN callee_id ELSE caller_id END IS NOT NULL
            ORDER BY veces DESC LIMIT 8
        """), {'u': uid}).fetchall()
        datos = _personas(s, [f[0] for f in filas if f[0]])
        salida = [dict(datos.get(f[0], {'id': f[0], 'nombre': 'Usuario', 'foto': '', 'cargo': ''}), veces=f[1])
                  for f in filas if f[0]]
        return jsonify({'success': True, 'personas': salida}), 200
    finally:
        s.close()


@bp_chat.route('/llamadas/favoritos', methods=['GET'])
@requiere_autenticacion
def favoritos_listar():
    uid = session.get('usuario_id')
    s = _sesion()
    try:
        ids = [f[0] for f in s.execute(text(
            "SELECT contacto_id FROM chat_llamadas_favoritos WHERE usuario_id = :u ORDER BY creado_en"),
            {'u': uid}).fetchall()]
        datos = _personas(s, ids)
        return jsonify({'success': True, 'personas': [datos[i] for i in ids if i in datos]}), 200
    finally:
        s.close()


@bp_chat.route('/llamadas/favoritos', methods=['POST'])
@requiere_autenticacion
def favoritos_agregar():
    uid = session.get('usuario_id')
    d = request.get_json(silent=True) or {}
    try:
        contacto = int(d.get('usuario_id') or 0)
    except (TypeError, ValueError):
        contacto = 0
    if not contacto or contacto == uid:
        return jsonify({'success': False, 'error': 'Persona no válida'}), 400
    s = _sesion()
    try:
        s.execute(text("INSERT INTO chat_llamadas_favoritos (usuario_id, contacto_id) VALUES (:u, :c) "
                       "ON CONFLICT DO NOTHING"), {'u': uid, 'c': contacto})
        s.commit()
        return jsonify({'success': True}), 201
    finally:
        s.close()


@bp_chat.route('/llamadas/favoritos/<int:contacto_id>', methods=['DELETE'])
@requiere_autenticacion
def favoritos_quitar(contacto_id):
    uid = session.get('usuario_id')
    s = _sesion()
    try:
        s.execute(text("DELETE FROM chat_llamadas_favoritos WHERE usuario_id = :u AND contacto_id = :c"),
                  {'u': uid, 'c': contacto_id})
        s.commit()
        return jsonify({'success': True}), 200
    finally:
        s.close()
