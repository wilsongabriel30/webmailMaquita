#!/opt/maquita-webmail/chat-service/venv/bin/python3
# -*- coding: utf-8 -*-
"""
Migración única del HISTÓRICO de adjuntos del chat al Drive de cada participante (T-18 fase 2).
Lee chat_message_media, descarga cada archivo desde FARO (donde vive el histórico) y lo refleja
con `drive_chat` (dedup en el Almacén). Idempotente: salta lo que ya tiene vínculo registrado.
Uso: migrar_adjuntos_drive.py [--dry-run]
"""
import os
import sys
import tempfile

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, 'app'))
for l in open(os.path.join(BASE, '.env'), encoding='utf-8'):
    l = l.strip()
    if l and not l.startswith('#') and '=' in l:
        k, v = l.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip())

import psycopg2
import psycopg2.extras
import requests

DRY = '--dry-run' in sys.argv
FARO = 'https://datos.maquita.com.ec'
MAIL = 'https://mail.maquita.org'


def url_candidatas(file_path):
    p = (file_path or '').replace('\\', '/')
    if p.startswith('http'):
        return [p]
    if p.startswith('static/'):
        return [f'{FARO}/{p}', f'{MAIL}/{p}']
    if p.startswith('/uploads/'):
        return [f'{FARO}{p}', f'{MAIL}{p}']
    if p.startswith('/'):
        return [f'{FARO}{p}']
    return [f'{FARO}/{p}']


def main():
    from interfaces.api import drive_chat, drive_eventos_api
    drive_eventos_api.asegurar_tabla()
    con = psycopg2.connect(os.environ['DATABASE_URL'])
    cur = con.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""SELECT md.id, md.file_path, md.file_name, m.conversation_id, m.sender_id
                   FROM chat_message_media md JOIN chat_messages m ON m.id = md.message_id
                   WHERE md.file_path LIKE '%uploads/chat/%' ORDER BY md.id""")
    filas = cur.fetchall()
    hechos = saltados = fallos = 0
    for f in filas:
        nombre_chat = drive_eventos_api._basename(f['file_path'])
        cur.execute("SELECT 1 FROM chat_media_drive WHERE nombre_chat = %s AND conversation_id = %s LIMIT 1", (nombre_chat, f['conversation_id']))
        if cur.fetchone():
            saltados += 1
            continue
        datos = None
        # 1) disco local del servicio (adjuntos subidos ya en la VM del chat)
        for local in (os.path.join(BASE, f['file_path'].lstrip('/')), os.path.join(BASE, 'app', 'interfaces', 'web', 'estaticos', f['file_path'].lstrip('/').replace('static/', '', 1))):
            if os.path.isfile(local):
                datos = open(local, 'rb').read(); break
        # 2) FARO / correo (histórico)
        for u in ([] if datos is not None else url_candidatas(f['file_path'])):
            try:
                r = requests.get(u, timeout=30)
                if r.status_code == 200 and r.content:
                    datos = r.content
                    break
            except requests.RequestException:
                pass
        if datos is None:
            fallos += 1
            print(f"FALLO {f['id']} {f['file_path']} (no descargable)")
            continue
        if DRY:
            print(f"(dry-run) migraría {f['file_path']} → conv {f['conversation_id']}")
            continue
        with tempfile.NamedTemporaryFile(delete=False, suffix='_' + nombre_chat) as tmp:
            tmp.write(datos)
            ruta_tmp = tmp.name
        try:
            drive_chat._reflejar(f['conversation_id'], f['sender_id'], [(ruta_tmp, f['file_name'] or nombre_chat)], nombre_chat=nombre_chat)
            hechos += 1
        finally:
            os.unlink(ruta_tmp)
    print(f"Resumen: {hechos} migrados, {saltados} ya vinculados, {fallos} fallos, de {len(filas)} adjuntos")


if __name__ == '__main__':
    main()
