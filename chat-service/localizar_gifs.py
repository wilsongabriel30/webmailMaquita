#!/opt/maquita-webmail/chat-service/venv/bin/python3
# -*- coding: utf-8 -*-
"""
Localizador de GIF del chat institucional.
==========================================
Los GIF del historial que apuntan a un CDN externo (Tenor, etc.) se descargan UNA
sola vez, quedan en la biblioteca local (`chat_gifs` + `estaticos/gifs/`) y los
mensajes se reescriben para apuntar al archivo local. Así el chat nunca vuelve a
consultar al tercero, aunque este cierre el servicio.

Se ejecuta a mano o cada noche por cron (ver /etc/cron.d/maquita-chat-gifs).
Idempotente: lo ya localizado no se repite; lo que falle se reintenta otra noche.
Uso: localizar_gifs.py [--dry-run]
"""
import os
import re
import sys
import uuid
import json
import urllib.request
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE, 'app'))

import psycopg2
import psycopg2.extras

DIR_GIFS = os.path.join(BASE, 'app', 'interfaces', 'web', 'estaticos', 'gifs')
URL_GIFS = '/static/gifs'
TAM_MAX = 40 * 1024 * 1024
DRY = '--dry-run' in sys.argv


def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def leer_env():
    ruta = os.path.join(BASE, '.env')
    if os.path.exists(ruta):
        for linea in open(ruta, encoding='utf-8'):
            linea = linea.strip()
            if linea and not linea.startswith('#') and '=' in linea:
                k, v = linea.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())


def etiquetas_desde_url(url):
    slug = os.path.splitext(url.rstrip('/').split('/')[-1])[0]
    partes = [p for p in re.split(r'[-_.\s%0-9]+', slug.lower()) if len(p) > 1]
    return ' '.join(sorted(set(partes))), (' '.join(partes)[:150] or 'GIF')


def descargar(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'MaquitaChat/1.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        datos = r.read(TAM_MAX + 1)
    if len(datos) > TAM_MAX:
        raise ValueError('archivo demasiado grande')
    if not datos.startswith((b'GIF87a', b'GIF89a', b'RIFF')):
        raise ValueError('no es GIF/WEBP')
    return datos


def main():
    leer_env()
    os.makedirs(DIR_GIFS, exist_ok=True)
    con = psycopg2.connect(os.environ['DATABASE_URL'])
    con.autocommit = False
    cur = con.cursor(cursor_factory=psycopg2.extras.DictCursor)

    cur.execute("ALTER TABLE chat_gifs ADD COLUMN IF NOT EXISTS origen_url TEXT")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_chat_gifs_origen ON chat_gifs (origen_url) WHERE origen_url IS NOT NULL")
    # Respaldo de lo que se va a reescribir (solo la primera vez que aparece cada fila)
    cur.execute("""CREATE TABLE IF NOT EXISTS bak_chat_gifs_externos (
                       tabla TEXT, fila_id INTEGER, valor_original TEXT, respaldado_en TIMESTAMP DEFAULT NOW(),
                       PRIMARY KEY (tabla, fila_id))""")
    con.commit()

    # 1) URLs externas pendientes: en metadata de mensajes y en adjuntos
    cur.execute("""SELECT id, metadata->>'gif_url' AS url FROM chat_messages
                   WHERE message_type = 'gif' AND metadata->>'gif_url' LIKE 'http%'""")
    mensajes = cur.fetchall()
    cur.execute("""SELECT id, file_path AS url FROM chat_message_media
                   WHERE file_path LIKE 'http%' AND (media_type IN ('gif','image') OR file_path ILIKE '%.gif%')""")
    adjuntos = cur.fetchall()
    urls = sorted({m['url'] for m in mensajes} | {a['url'] for a in adjuntos})
    log(f"GIF externos: {len(mensajes)} mensajes, {len(adjuntos)} adjuntos, {len(urls)} URL distintas")

    # 2) Descargar cada URL una sola vez
    locales = {}
    cur.execute("SELECT origen_url, archivo FROM chat_gifs WHERE origen_url IS NOT NULL")
    for f in cur.fetchall():
        locales[f['origen_url']] = f"{URL_GIFS}/{f['archivo']}"
    ok = fallos = 0
    for url in urls:
        if url in locales:
            continue
        try:
            if DRY:
                log(f"(dry-run) descargaría {url}")
                continue
            datos = descargar(url)
            ext = '.webp' if datos.startswith(b'RIFF') else '.gif'
            nombre = f"{datetime.now():%Y%m%d}_{uuid.uuid4().hex[:12]}{ext}"
            with open(os.path.join(DIR_GIFS, nombre), 'wb') as f:
                f.write(datos)
            etiquetas, titulo = etiquetas_desde_url(url)
            cur.execute("INSERT INTO chat_gifs (archivo, titulo, etiquetas, subido_por, origen_url) VALUES (%s,%s,%s,NULL,%s)",
                        (nombre, titulo, etiquetas, url))
            con.commit()
            locales[url] = f"{URL_GIFS}/{nombre}"
            ok += 1
            log(f"localizado {url} -> {nombre} ({len(datos)//1024} KB)")
        except Exception as e:
            con.rollback()
            fallos += 1
            log(f"FALLO {url}: {e}")

    # 3) Reescribir mensajes y adjuntos hacia el archivo local
    reescritos = 0
    if not DRY:
        for m in mensajes:
            local = locales.get(m['url'])
            if not local:
                continue
            cur.execute("INSERT INTO bak_chat_gifs_externos (tabla, fila_id, valor_original) VALUES ('chat_messages', %s, %s) ON CONFLICT DO NOTHING",
                        (m['id'], m['url']))
            cur.execute("UPDATE chat_messages SET metadata = jsonb_set(COALESCE(metadata,'{}')::jsonb, '{gif_url}', %s::jsonb) WHERE id = %s",
                        (json.dumps(local), m['id']))
            reescritos += 1
        for a in adjuntos:
            local = locales.get(a['url'])
            if not local:
                continue
            cur.execute("INSERT INTO bak_chat_gifs_externos (tabla, fila_id, valor_original) VALUES ('chat_message_media', %s, %s) ON CONFLICT DO NOTHING",
                        (a['id'], a['url']))
            cur.execute("UPDATE chat_message_media SET file_path = %s WHERE id = %s", (local, a['id']))
            reescritos += 1
        con.commit()
    log(f"Resumen: {ok} descargados, {fallos} fallos, {reescritos} referencias reescritas a local")
    con.close()


if __name__ == '__main__':
    main()
