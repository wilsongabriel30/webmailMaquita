# -*- coding: utf-8 -*-
"""
Métrica de llamadas 1a1 (T-25): cuántas conectan directas (p2p) y cuántas por el servidor (sfu) y por qué.
POST /api/chat/llamada/metrica {room, modo: p2p|sfu, motivo, tipo, role}  (sesión del chat)
GET  /api/chat/llamada/metrica/resumen?dias=30  → totales por modo y motivo
Tabla `chat_llamadas_metricas` (se crea sola).
"""
import os

import psycopg2
from flask import Blueprint, jsonify, request, session

bp_metricas_llamadas = Blueprint('metricas_llamadas', __name__, url_prefix='/api/chat/llamada/metrica')


def _con():
    return psycopg2.connect(os.environ['DATABASE_URL'])


def asegurar_tabla():
    with _con() as con, con.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS chat_llamadas_metricas (
                           id SERIAL PRIMARY KEY, usuario_id INTEGER, room VARCHAR(80), modo VARCHAR(10) NOT NULL,
                           motivo VARCHAR(40), tipo VARCHAR(10), role VARCHAR(10), creado_en TIMESTAMP NOT NULL DEFAULT NOW());
                       CREATE INDEX IF NOT EXISTS ix_cllm_creado ON chat_llamadas_metricas (creado_en)""")


@bp_metricas_llamadas.route('', methods=['POST'])
def registrar():
    uid = session.get('usuario_id')
    if not uid:
        return jsonify({'success': False, 'error': 'No autorizado'}), 401
    d = request.get_json(silent=True) or {}
    modo = (d.get('modo') or '')[:10]
    if modo not in ('p2p', 'sfu'):
        return jsonify({'success': False, 'error': 'modo inválido'}), 400
    try:
        with _con() as con, con.cursor() as cur:
            cur.execute("INSERT INTO chat_llamadas_metricas (usuario_id, room, modo, motivo, tipo, role) VALUES (%s,%s,%s,%s,%s,%s)",
                        (int(uid), (d.get('room') or '')[:80], modo, (d.get('motivo') or '')[:40], (d.get('tipo') or '')[:10], (d.get('role') or '')[:10]))
    except Exception as e:
        print(f'[metricas-llamadas] {e}')
    return jsonify({'success': True})


@bp_metricas_llamadas.route('/resumen', methods=['GET'])
def resumen():
    if not session.get('usuario_id'):
        return jsonify({'success': False, 'error': 'No autorizado'}), 401
    try:
        dias = max(1, min(int(request.args.get('dias', 30)), 365))
    except ValueError:
        dias = 30
    with _con() as con, con.cursor() as cur:
        cur.execute("""SELECT modo, motivo, COUNT(*) FROM chat_llamadas_metricas
                       WHERE creado_en >= NOW() - (%s || ' days')::interval GROUP BY 1, 2 ORDER BY 1, 3 DESC""", (str(dias),))
        filas = [{'modo': m, 'motivo': mo, 'total': n} for m, mo, n in cur.fetchall()]
    p2p = sum(f['total'] for f in filas if f['modo'] == 'p2p'); sfu = sum(f['total'] for f in filas if f['modo'] == 'sfu')
    return jsonify({'success': True, 'dias': dias, 'p2p': p2p, 'sfu': sfu,
                    'porcentaje_p2p': round(p2p * 100 / (p2p + sfu), 1) if (p2p + sfu) else 0, 'detalle': filas})
