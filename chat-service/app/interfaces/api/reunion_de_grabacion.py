"""
T-30 (10/11/2026): toda grabación del chat (llamada directa o conferencia de grupo) queda ligada a una reunión.

Una llamada no crea reunión. Al terminar de subir su grabación al Drive, aquí se crea una reunión «de registro» en
reuniones_programadas, con config_sala.origen = 'grabacion'. Raíces no la usa para dar acceso ni para avisos: es solo historial.

- Llamada directa (room «llamada_<a>_<b>»): la sala se repite siempre entre las mismas dos personas, así que NO se busca por
  nombre. Cada llamada grabada tiene su reunión. Si se graba otra vez en la misma llamada (menos de 15 min después de crear la
  reunión), la grabación se añade a esa misma reunión.
- Conferencia (room «conf_<marca>_<id>», única): una reunión por sala.
Lo usa grabaciones_drive._procesar cuando _contexto no encontró reunión.
Equivalente para Meet (salas instantáneas): modulos/jitsi/aplicacion/servicios/reunion_de_grabacion.py (Raíces, VM 101).
"""
import json
import os
from datetime import datetime

import psycopg2

ORIGEN = 'grabacion'
REUSAR_MINUTOS = 15


def _con():
    return psycopg2.connect(os.environ['DATABASE_URL'])


def reunion_para_grabacion(fila, asunto, creador, ids, correos):
    """Devuelve el id de la reunión de registro (la crea si hace falta), o None si no se pudo."""
    room = (fila.get('room') or '')[:100]
    if not room or not creador:
        return None
    cuando = fila.get('creado_en') or datetime.now()
    llamada = room.startswith('llamada_')
    try:
        with _con() as con, con.cursor() as cur:
            if llamada:
                cur.execute("""SELECT id FROM reuniones_programadas
                               WHERE nombre_sala = %s AND config_sala->>'origen' = %s
                                 AND created_at >= %s::timestamp - make_interval(mins => %s)
                               ORDER BY id DESC LIMIT 1""", (room, ORIGEN, cuando, REUSAR_MINUTOS))
            else:
                cur.execute("SELECT id FROM reuniones_programadas WHERE nombre_sala = %s ORDER BY id DESC LIMIT 1", (room,))
            r = cur.fetchone()
            if r:
                return r[0]
            if llamada:
                personas = [int(x) for x in room.split('_')[1:] if x.isdigit()]
                cur.execute("SELECT id, coalesce(nullif(full_name, ''), username) FROM usuarios WHERE id = ANY(%s)", (personas,))
                nombres = dict(cur.fetchall())
                titulo = 'Llamada ' + ' – '.join(nombres.get(p, str(p)) for p in personas)
            else:
                titulo = asunto if asunto and asunto != room else 'Llamada grupal'
            cfg = {'origen': ORIGEN, 'tipo': 'llamada' if llamada else 'conferencia',
                   'conversation_id': fila.get('conversation_id'), 'chat_grabacion_id': fila.get('id')}
            cur.execute("""INSERT INTO reuniones_programadas
                               (asunto, nombre_sala, fecha_hora, duracion_horas, creador_id, participantes_emails, config_sala, estado)
                           VALUES (%s, %s, %s, 1, %s, %s, %s::jsonb, 'programada') RETURNING id""",
                        (titulo[:200], room, cuando, creador, ','.join(sorted(c for c in correos if c)), json.dumps(cfg)))
            return cur.fetchone()[0]
    except Exception as e:
        print(f'[grabaciones] reunión de registro para {room}: {e}')
        return None
