# -*- coding: utf-8 -*-
"""Preferencias de cada persona para el chat y las llamadas (T-101, 11/11/2026).

Sirven para que lo que alguien elige en un equipo (tono de llamada, volumen, tema) le siga a los demás.
Solo se guardan valores cortos de una lista cerrada; los archivos de sonido propios NO salen del equipo.

- GET /api/chat/preferencias        → {"exito": true, "preferencias": {...}, "admitidas": {...}}
- PUT /api/chat/preferencias        → cuerpo {"clave": valor, ...}; mezcla con lo guardado. `null` borra esa clave.
  (también POST, para clientes que no envían PUT)
- Evento Socket.IO `preferencias` en la sala `user_<id>` con el conjunto completo, para los otros equipos de la persona.
"""
import json
import os
import re

import psycopg2
from flask import jsonify, request

from interfaces.api.chat_base import bp_chat, obtener_usuario_id, requiere_autenticacion

_tabla_lista = False
_NOMBRE = re.compile(r'^[A-Za-z0-9áéíóúñÁÉÍÓÚÑüÜ _.\-]{1,60}$')

# clave -> (tipo, descripción). Lo que no esté aquí se rechaza.
ADMITIDAS = {
    'tono_llamada': ('nombre', 'Tono de las llamadas: nombre de un tono incluido en la app, o «propio» si es un archivo del equipo'),
    'tono_grupo': ('nombre', 'Tono de las llamadas de grupo'),
    'tono_mensaje': ('nombre', 'Sonido de los mensajes'),
    'volumen_timbre': ('porcentaje', 'Volumen del timbre, de 0 a 100'),
    'timbre_en_no_molestar': ('booleano', 'Si el timbre suena con el estado «No molestar»'),
    'tema': ('tema', 'clasico | fluent | fluent-oscuro | fluent-auto'),
    'mini_ventana': ('booleano', 'Mostrar la mini ventana de la llamada al minimizar'),
}
_TEMAS = ('clasico', 'fluent', 'fluent-oscuro', 'fluent-auto')


def _conexion():
    return psycopg2.connect(os.environ['DATABASE_URL'])


def _asegurar_tabla(cur):
    global _tabla_lista
    if _tabla_lista:
        return
    cur.execute("""CREATE TABLE IF NOT EXISTS chat_preferencias_usuario (
                       usuario_id INTEGER PRIMARY KEY,
                       datos JSONB NOT NULL DEFAULT '{}'::jsonb,
                       actualizado_en TIMESTAMP NOT NULL DEFAULT NOW())""")
    _tabla_lista = True


def _validar(clave, valor):
    """Devuelve (ok, valor_limpio | motivo)."""
    tipo = ADMITIDAS[clave][0]
    if tipo == 'nombre':
        if isinstance(valor, str) and _NOMBRE.match(valor.strip()):
            return True, valor.strip()
        return False, 'debe ser un nombre corto (letras, números, espacios, punto, guion; hasta 60)'
    if tipo == 'porcentaje':
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not 0 <= valor <= 100:
            return False, 'debe ser un número de 0 a 100'
        return True, int(valor)
    if tipo == 'booleano':
        return (True, valor) if isinstance(valor, bool) else (False, 'debe ser true o false')
    if tipo == 'tema':
        return (True, valor) if valor in _TEMAS else (False, 'debe ser uno de: ' + ', '.join(_TEMAS))
    return False, 'tipo desconocido'


def leer(usuario_id):
    try:
        with _conexion() as con, con.cursor() as cur:
            _asegurar_tabla(cur)
            cur.execute("SELECT datos FROM chat_preferencias_usuario WHERE usuario_id = %s", (usuario_id,))
            f = cur.fetchone()
        datos = f[0] if f else {}
        if isinstance(datos, str):
            datos = json.loads(datos)
        return {k: v for k, v in (datos or {}).items() if k in ADMITIDAS}
    except Exception as e:
        print(f'[preferencias] leer {usuario_id}: {e}')
        return {}


def _avisar(usuario_id, datos):
    try:
        from interfaces.websocket import manejador_websocket as mw
        if mw.socketio:
            mw.socketio.emit('preferencias', {'preferencias': datos}, room=f'user_{int(usuario_id)}')
    except Exception as e:
        print(f'[preferencias] aviso: {e}')


@bp_chat.route('/preferencias', methods=['GET'])
@requiere_autenticacion
def obtener_preferencias():
    return jsonify({'exito': True, 'preferencias': leer(obtener_usuario_id()),
                    'admitidas': {k: v[1] for k, v in ADMITIDAS.items()}}), 200


@bp_chat.route('/preferencias', methods=['PUT', 'POST'])
@requiere_autenticacion
def guardar_preferencias():
    usuario_id = obtener_usuario_id()
    cuerpo = request.get_json(silent=True)
    if not isinstance(cuerpo, dict) or not cuerpo:
        return jsonify({'exito': False, 'mensaje': 'Envía un objeto con las preferencias a cambiar'}), 400
    errores, cambios, borrar = {}, {}, []
    for clave, valor in cuerpo.items():
        if clave not in ADMITIDAS:
            errores[str(clave)[:40]] = 'preferencia no admitida'
        elif valor is None:
            borrar.append(clave)
        else:
            ok, limpio = _validar(clave, valor)
            if ok:
                cambios[clave] = limpio
            else:
                errores[clave] = limpio
    if errores:
        return jsonify({'exito': False, 'mensaje': 'Hay preferencias no válidas', 'errores': errores}), 400
    try:
        actuales = leer(usuario_id)
        actuales.update(cambios)
        for clave in borrar:
            actuales.pop(clave, None)
        with _conexion() as con, con.cursor() as cur:
            _asegurar_tabla(cur)
            cur.execute("""INSERT INTO chat_preferencias_usuario (usuario_id, datos, actualizado_en) VALUES (%s, %s::jsonb, NOW())
                           ON CONFLICT (usuario_id) DO UPDATE SET datos = EXCLUDED.datos, actualizado_en = NOW()""",
                        (usuario_id, json.dumps(actuales, ensure_ascii=False)))
    except Exception as e:
        print(f'[preferencias] guardar {usuario_id}: {e}')
        return jsonify({'exito': False, 'mensaje': 'No se pudieron guardar las preferencias'}), 500
    _avisar(usuario_id, actuales)
    return jsonify({'exito': True, 'preferencias': actuales}), 200
