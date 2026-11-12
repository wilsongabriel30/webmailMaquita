# -*- coding: utf-8 -*-
"""Contadores para la app de escritorio y la web (T-101, 11/11/2026).

Evento Socket.IO **`contadores`** en la sala `user_<id>`: {"no_leidos": N, "perdidas": N, "fecha": ISO}.
Va en un evento PROPIO (no en `notificacion`) para que ninguna versión de la app lo confunda con un aviso.

- no_leidos: suma de mensajes sin leer de las conversaciones activas de la persona.
- perdidas: llamadas que no contestó (sin_respuesta o rechazada) desde la última vez que abrió la sección «Llamadas».
  La primera vez que se pregunta por alguien se toma «ahora» como punto de partida, para no arrancar con un número viejo.

Se emite cuando cambia algo: mensaje nuevo (lo llama notificaciones_globales.notificar_mensaje), marcar leído,
registrar una llamada y abrir «Llamadas». También se puede pedir:
- GET  /api/chat/contadores                  → los dos números
- POST /api/chat/llamadas/perdidas/vistas    → pone las perdidas a cero (lo hace la sección «Llamadas» al abrirse)
"""
import os
import re
from datetime import datetime

import psycopg2
from flask import jsonify, request

from interfaces.api.chat_base import bp_chat, obtener_usuario_id, requiere_autenticacion

_tabla_lista = False
_RUTAS_QUE_CAMBIAN = re.compile(r'/(read|mark-all-read|llamadas/registrar|llamadas/perdidas/vistas)/?$')


def _conexion():
    return psycopg2.connect(os.environ['DATABASE_URL'])


def _asegurar_tabla(cur):
    global _tabla_lista
    if _tabla_lista:
        return
    cur.execute("""CREATE TABLE IF NOT EXISTS chat_llamadas_vistas (
                       usuario_id INTEGER PRIMARY KEY,
                       visto_en TIMESTAMP NOT NULL DEFAULT NOW())""")
    _tabla_lista = True


def contar(usuario_id):
    """{'no_leidos': N, 'perdidas': N} de una persona. Ante cualquier fallo, ceros: un contador no rompe nada."""
    try:
        with _conexion() as con, con.cursor() as cur:
            _asegurar_tabla(cur)
            cur.execute("""SELECT COALESCE(SUM(GREATEST(unread_count, 0)), 0) FROM chat_participants
                           WHERE user_id = %s AND is_active AND NOT COALESCE(is_archived, FALSE)""", (usuario_id,))
            no_leidos = int(cur.fetchone()[0] or 0)
            cur.execute("INSERT INTO chat_llamadas_vistas (usuario_id) VALUES (%s) ON CONFLICT (usuario_id) DO NOTHING", (usuario_id,))
            cur.execute("""SELECT COUNT(*) FROM chat_llamadas l, chat_llamadas_vistas v
                           WHERE v.usuario_id = %s AND l.callee_id = %s
                             AND l.estado IN ('sin_respuesta', 'rechazada') AND l.creado_en > v.visto_en""", (usuario_id, usuario_id))
            perdidas = int(cur.fetchone()[0] or 0)
        return {'no_leidos': no_leidos, 'perdidas': perdidas}
    except Exception as e:
        print(f'[contadores] contar {usuario_id}: {e}')
        return {'no_leidos': 0, 'perdidas': 0}


def marcar_perdidas_vistas(usuario_id):
    try:
        with _conexion() as con, con.cursor() as cur:
            _asegurar_tabla(cur)
            cur.execute("""INSERT INTO chat_llamadas_vistas (usuario_id, visto_en) VALUES (%s, NOW())
                           ON CONFLICT (usuario_id) DO UPDATE SET visto_en = NOW()""", (usuario_id,))
    except Exception as e:
        print(f'[contadores] vistas {usuario_id}: {e}')


def emitir_contadores(usuario_ids, espera=0.8):
    """Emite `contadores` a cada persona. Espera un instante: quien llama suele estar aún dentro de su transacción."""
    try:
        from interfaces.websocket import manejador_websocket as mw
        sio = mw.socketio
        ids = sorted({int(u) for u in (usuario_ids or []) if u})
        if not sio or not ids:
            return

        def tarea():
            try:
                if espera:
                    sio.sleep(espera)
                for uid in ids:
                    datos = contar(uid)
                    datos['fecha'] = datetime.now().isoformat(timespec='seconds')
                    sio.emit('contadores', datos, room=f'user_{uid}')
            except Exception as e:
                print(f'[contadores] emitir: {e}')
        sio.start_background_task(tarea)
    except Exception as e:
        print(f'[contadores] {e}')


@bp_chat.route('/contadores', methods=['GET'])
@requiere_autenticacion
def obtener_contadores():
    return jsonify(dict(contar(obtener_usuario_id()), exito=True)), 200


@bp_chat.route('/llamadas/perdidas/vistas', methods=['POST'])
@requiere_autenticacion
def perdidas_vistas():
    uid = obtener_usuario_id()
    marcar_perdidas_vistas(uid)
    return jsonify(dict(contar(uid), exito=True)), 200


@bp_chat.after_request
def _avisar_si_cambian(respuesta):
    """Tras marcar leído, registrar una llamada o abrir «Llamadas», se reenvían los contadores a quien toca."""
    try:
        if request.method == 'POST' and respuesta.status_code < 400 and _RUTAS_QUE_CAMBIAN.search(request.path or ''):
            ids = [obtener_usuario_id()]
            if request.path.rstrip('/').endswith('llamadas/registrar'):
                cuerpo = request.get_json(silent=True) or {}
                if str(cuerpo.get('peer_id') or '').isdigit():
                    ids.append(int(cuerpo['peer_id']))
            emitir_contadores(ids)
    except Exception as e:
        print(f'[contadores] aviso: {e}')
    return respuesta
