# -*- coding: utf-8 -*-
"""
Recordatorios de reuniones (T-04): 10 minutos antes de cada reunión programada se
emite `notificacion` (tipo `reunion`) al creador y a los participantes internos.
Corre como tarea de fondo del servidor (revisa cada 60 s). Idempotente gracias a la
tabla `reuniones_avisos`.
"""
import os
from datetime import datetime

import psycopg2
import psycopg2.extras

MINUTOS_ANTES = 10


def _conexion():
    return psycopg2.connect(os.environ['DATABASE_URL'])


def asegurar_tabla():
    with _conexion() as con, con.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS reuniones_avisos (
                           reunion_id INTEGER NOT NULL, tipo VARCHAR(30) NOT NULL,
                           enviado_en TIMESTAMP NOT NULL DEFAULT NOW(), PRIMARY KEY (reunion_id, tipo))""")


def _ciclo():
    from interfaces.websocket.notificaciones_globales import emitir, usuarios_por_correo
    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("""SELECT r.* FROM reuniones_programadas r
                       WHERE r.estado <> 'cancelada'
                         AND r.fecha_hora BETWEEN NOW() AND NOW() + (%s || ' minutes')::interval
                         AND NOT EXISTS (SELECT 1 FROM reuniones_avisos a WHERE a.reunion_id = r.id AND a.tipo = '10min')""",
                    (MINUTOS_ANTES,))
        filas = cur.fetchall()
        for r in filas:
            correos = [e.strip().lower() for e in (r['participantes_emails'] or '').split(',') if e.strip()]
            ids = set(usuarios_por_correo(correos)) | {r['creador_id']}
            minutos = max(1, int((r['fecha_hora'] - datetime.now()).total_seconds() // 60))
            emitir(ids, 'reunion', f"En {minutos} min: {r['asunto'] or 'Reunión'}",
                   f"{r['fecha_hora']:%H:%M} · Meet Maquita",
                   f"https://mail.maquita.org/api/chat/reuniones/{r['id']}/acceso?redirigir=1",
                   {'origen': 'reuniones', 'reunion_id': r['id'], 'sala': r['nombre_sala'],
                    'inicio': r['fecha_hora'].isoformat(timespec='minutes'), 'recordatorio': True})
            cur.execute("INSERT INTO reuniones_avisos (reunion_id, tipo) VALUES (%s, '10min') ON CONFLICT DO NOTHING", (r['id'],))
            print(f"[recordatorios] reunión {r['id']} avisada a {len(ids)} usuarios")


def iniciar(socketio):
    """Lanza el bucle como tarea de fondo compatible con eventlet."""
    asegurar_tabla()

    def bucle():
        while True:
            try:
                _ciclo()
            except Exception as e:
                print(f'[recordatorios] error: {e}')
            socketio.sleep(60)

    socketio.start_background_task(bucle)
