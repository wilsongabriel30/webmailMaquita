# -*- coding: utf-8 -*-
"""
Grabaciones ligadas al registro → Drive del creador (T-30 fase 2, contrato de RESPUESTAS-SERVIDOR).
Al detener una grabación (LiveKit Egress): en segundo plano espera a que el MP4 esté completo en el CT 210, lo sube al
Drive del solicitante en «/Grabaciones de reuniones/<AAAA-MM>/<AAAA-MM-DD HHMM> <asunto|sala>.mp4» (dedup del almacén),
registra `reuniones_grabaciones`, comparte en solo lectura con los participantes internos y avisa por T-03
«Grabación lista». Retención: 12 meses (columna `vence_en`; la purga la hace `purgar_grabaciones()`, cron mensual).
Depende de: ALMACEN_URL / ALMACEN_SECRETO_INTERNO (.env), LIVEKIT_GRABACIONES_URL (http://193.16.0.27:8081).
"""
import os
import re
import tempfile
import threading
import time
from datetime import datetime, timedelta

import psycopg2
import psycopg2.extras
import requests

from interfaces.api.drive_chat import _asegurar_carpeta, _subir, _cab, _ALMACEN

CARPETA = 'Grabaciones de reuniones'
_GRAB = os.getenv('LIVEKIT_GRABACIONES_URL', 'http://193.16.0.27:8081').rstrip('/')
RETENCION_DIAS = int(os.getenv('GRABACIONES_RETENCION_DIAS', '365'))


def _con():
    return psycopg2.connect(os.environ['DATABASE_URL'])


def asegurar_tabla():
    with _con() as con, con.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS reuniones_grabaciones (
                           id SERIAL PRIMARY KEY, grabacion_id INTEGER, reunion_id INTEGER, conversation_id INTEGER,
                           usuario_id INTEGER NOT NULL, room VARCHAR(120), ruta_drive TEXT NOT NULL, bytes BIGINT DEFAULT 0,
                           compartida_con TEXT, creado_en TIMESTAMP NOT NULL DEFAULT NOW(), vence_en TIMESTAMP, conservar BOOLEAN DEFAULT FALSE);
                       ALTER TABLE chat_grabaciones ADD COLUMN IF NOT EXISTS conversation_id INTEGER;
                       ALTER TABLE chat_grabaciones ADD COLUMN IF NOT EXISTS ruta_drive TEXT""")


def _nombre_seguro(t, maximo=60):
    t = re.sub(r'[\\/:*?"<>|\r\n\t]+', ' ', str(t or '')).strip().strip('.')
    return re.sub(r'\s+', ' ', t)[:maximo] or 'Reunión'


def _contexto(fila):
    """(asunto, reunion_id, participantes_ids, correos) según el room: reunión Meet, conferencia de un grupo o llamada 1a1."""
    room = fila['room'] or ''
    asunto, reunion_id, ids, correos = None, None, set(), set()
    with _con() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("SELECT id, asunto, participantes_emails, creador_id FROM reuniones_programadas WHERE nombre_sala = %s ORDER BY id DESC LIMIT 1", (room,))
        r = cur.fetchone()
        if r:
            asunto, reunion_id = r['asunto'], r['id']
            correos |= {e.strip().lower() for e in (r['participantes_emails'] or '').split(',') if e.strip()}
            ids.add(r['creador_id'])
        if room.startswith('llamada_'):
            ids |= {int(x) for x in room.split('_')[1:] if x.isdigit()}
            asunto = asunto or 'Llamada'
        if fila.get('conversation_id'):
            cur.execute("SELECT name, conversation_type FROM chat_conversations WHERE id = %s", (fila['conversation_id'],))
            c = cur.fetchone()
            cur.execute("SELECT user_id FROM chat_participants WHERE conversation_id = %s AND is_active", (fila['conversation_id'],))
            ids |= {x[0] for x in cur.fetchall()}
            if c and not asunto:
                asunto = c['name'] or ('Llamada' if c['conversation_type'] == 'direct' else 'Llamada grupal')
        if ids:
            cur.execute("SELECT id, lower(email) FROM usuarios WHERE id = ANY(%s)", (list(ids),))
            correos |= {e for _, e in cur.fetchall() if e}
    return asunto or room, reunion_id, ids, correos


def _esperar_mp4(archivo, maximo_s=900):
    """Espera a que el egress termine de escribir: tamaño estable en dos lecturas separadas 15 s."""
    url = f'{_GRAB}/{archivo}'
    t0, previo = time.time(), -1
    while time.time() - t0 < maximo_s:
        try:
            r = requests.head(url, timeout=10)
            if r.status_code == 200:
                tam = int(r.headers.get('Content-Length') or 0)
                if tam > 0 and tam == previo:
                    return url, tam
                previo = tam
        except requests.RequestException:
            pass
        time.sleep(15)
    return None, 0


def _compartir(usuario_id, ruta, correo):
    try:
        requests.post(f'{_ALMACEN}/api/almacen/compartir', json={'ruta': ruta, 'tipo': 0, 'permisos': 1, 'con_quien': correo},
                      headers=_cab(usuario_id), timeout=20)
    except requests.RequestException:
        pass


def _procesar(egress_id):
    try:
        with _con() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM chat_grabaciones WHERE egress_id = %s", (egress_id,))
            fila = cur.fetchone()
        if not fila or fila.get('ruta_drive'):
            return
        fila = dict(fila)
        url, tam = _esperar_mp4(fila['archivo'])
        if not url:
            print(f'[grabaciones] {egress_id}: el MP4 no apareció')
            return
        asunto, reunion_id, ids, correos = _contexto(fila)
        creador = int(fila['solicitante_id'])
        cuando = fila['creado_en'] or datetime.now()
        sub = cuando.strftime('%Y-%m')
        nombre = f"{cuando:%Y-%m-%d %H%M} {_nombre_seguro(asunto)}.mp4"
        _asegurar_carpeta(creador, '/', CARPETA)
        _asegurar_carpeta(creador, '/' + CARPETA, sub)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp:
            with requests.get(url, stream=True, timeout=60) as r:
                for trozo in r.iter_content(1 << 20):
                    tmp.write(trozo)
            ruta_tmp = tmp.name
        try:
            ruta_drive = _subir(creador, f'/{CARPETA}/{sub}', ruta_tmp, nombre)
        finally:
            os.unlink(ruta_tmp)
        if not ruta_drive:
            print(f'[grabaciones] {egress_id}: no se pudo subir al Drive')
            return
        with _con() as con, con.cursor() as cur:
            cur.execute("SELECT lower(email) FROM usuarios WHERE id = %s", (creador,))
            mi = cur.fetchone()
        mi_correo = (mi[0] if mi else '') or ''
        compartida = []   # decisión de sistemas (28/08): no se comparte automáticamente; compartir es del creador desde el Drive
        participantes = sorted(c for c in correos if c and c != mi_correo)
        with _con() as con, con.cursor() as cur:
            cur.execute("""INSERT INTO reuniones_grabaciones (grabacion_id, reunion_id, conversation_id, usuario_id, room, ruta_drive, bytes, compartida_con, vence_en)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (fila['id'], reunion_id, fila.get('conversation_id'), creador, fila['room'], ruta_drive, tam, 'participantes: ' + ', '.join(participantes),
                         datetime.now() + timedelta(days=RETENCION_DIAS)))
            cur.execute("UPDATE chat_grabaciones SET ruta_drive = %s, estado = 'en_drive' WHERE id = %s", (ruta_drive, fila['id']))
        try:
            from interfaces.websocket.notificaciones_globales import emitir
            emitir([creador], 'sistema', 'Grabación lista', f'«{nombre}» quedó en tu Drive, en {CARPETA}/{sub}. Compártela desde el Drive si lo deseas.',
                   'https://datos.maquita.com.ec/archivos-almacen?app=1', {'origen': 'grabaciones', 'ruta': ruta_drive, 'reunion_id': reunion_id})
        except Exception as e:
            print(f'[grabaciones] aviso: {e}')
        print(f'[grabaciones] {egress_id} → {ruta_drive} ({tam} bytes)')
    except Exception as e:
        print(f'[grabaciones] {egress_id}: {e}')


def programar_a_drive(egress_id):
    """Dispara y olvida: se llama al detener la grabación."""
    if egress_id:
        threading.Thread(target=_procesar, args=(egress_id,), daemon=True).start()


def purgar_grabaciones():
    """Vencidas (12 meses) y no marcadas «conservar» → papelera del Drive del creador (90 días de retención de sistemas)."""
    n = 0
    with _con() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("SELECT id, usuario_id, ruta_drive FROM reuniones_grabaciones WHERE vence_en < NOW() AND NOT conservar")
        for g in cur.fetchall():
            try:
                requests.delete(f'{_ALMACEN}/api/almacen/archivos', params={'ruta': g['ruta_drive']}, headers=_cab(g['usuario_id']), timeout=30)
                cur.execute("UPDATE reuniones_grabaciones SET conservar = TRUE, compartida_con = COALESCE(compartida_con,'') || ' [vencida→papelera]' WHERE id = %s", (g['id'],))
                n += 1
            except Exception as e:
                print(f'[grabaciones] purga {g["id"]}: {e}')
    return n
