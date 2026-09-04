# -*- coding: utf-8 -*-
"""
Archivos del chat → Drive Maquita de cada usuario (T-18, fase 1).
==================================================================
Cada archivo enviado por el chat se refleja en el Drive del EMISOR y de cada RECEPTOR en
`/Archivos del chat/<conversación>/`. El Almacén deduplica por hash (una sola copia física
en pve-storage aunque se refleje a N personas) y la carpeta raíz está protegida.
Se ejecuta en segundo plano: nunca retrasa ni rompe el envío del mensaje.

Variables (.env): ALMACEN_URL (http://193.16.0.21:8788), ALMACEN_SECRETO_INTERNO.
"""
import os
import re
import threading

import psycopg2
import psycopg2.extras
import requests

CARPETA = 'Archivos del chat'
_ALMACEN = os.getenv('ALMACEN_URL', 'http://193.16.0.21:8788').rstrip('/')
_SECRETO = os.getenv('ALMACEN_SECRETO_INTERNO', '')
_TIMEOUT = 20


def _conexion():
    return psycopg2.connect(os.environ['DATABASE_URL'])


def _cab(usuario_id):
    return {'X-Almacen-Interno': _SECRETO, 'X-Almacen-Interno-Usuario': str(int(usuario_id))}


def _nombre_seguro(texto, maximo=60):
    t = re.sub(r'[\\/:*?"<>|\r\n\t]+', ' ', str(texto or '')).strip().strip('.')
    t = re.sub(r'\s+', ' ', t)
    return (t or 'Conversación')[:maximo]


def _contexto(conversacion_id):
    """(nombre de carpeta por conversación, {usuario_id: nombre}) — para directos, la carpeta es 'Con <otro>'."""
    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("SELECT id, name, conversation_type, description FROM chat_conversations WHERE id = %s", (conversacion_id,))
        c = cur.fetchone()
        cur.execute("""SELECT p.user_id, COALESCE(NULLIF(TRIM(u.full_name), ''), u.username, u.email) AS nombre
                       FROM chat_participants p JOIN usuarios u ON u.id = p.user_id
                       WHERE p.conversation_id = %s AND p.is_active""", (conversacion_id,))
        miembros = {r['user_id']: r['nombre'] for r in cur.fetchall()}
    if not c:
        return None, {}
    if c['description'] == 'notas-personales':
        return {uid: 'Mis notas' for uid in miembros}, miembros
    if c['conversation_type'] == 'group':
        nombre = _nombre_seguro(c['name'] or f'Grupo {c["id"]}')
        return {uid: nombre for uid in miembros}, miembros
    # Directo: cada uno ve la carpeta con el nombre del otro
    carpetas = {}
    for uid in miembros:
        otros = [n for u, n in miembros.items() if u != uid]
        carpetas[uid] = _nombre_seguro('Con ' + (otros[0] if otros else 'contacto'))
    return carpetas, miembros


def _asegurar_carpeta(usuario_id, ruta_padre, nombre):
    try:
        requests.post(f'{_ALMACEN}/api/almacen/carpetas', json={'ruta': ruta_padre, 'nombre': nombre},
                      headers=_cab(usuario_id), timeout=_TIMEOUT)
    except requests.RequestException:
        pass


def _subir(usuario_id, carpeta, ruta_local, nombre):
    """Devuelve la ruta virtual con la que quedó en el Drive (None si falló)."""
    with open(ruta_local, 'rb') as f:
        r = requests.post(f'{_ALMACEN}/api/almacen/archivos', data={'carpeta': carpeta},
                          files={'archivo': (nombre, f)}, headers=_cab(usuario_id), timeout=120)
    if r.status_code not in (200, 201):
        return None
    try:
        arch = (r.json() or {}).get('archivos') or []
        return arch[0].get('ruta') if arch else f'{carpeta}/{nombre}'
    except ValueError:
        return f'{carpeta}/{nombre}'


def _reflejar(conversacion_id, remitente_id, archivos, nombre_chat=None):
    """archivos: [(ruta_local, nombre_original)]. nombre_chat: nombre con el que el CHAT guarda el archivo
    (basename de file_path); por defecto el basename de ruta_local. Sirve para vincular Drive ↔ chat (fase 2)."""
    if not _SECRETO:
        return
    try:
        carpetas, miembros = _contexto(conversacion_id)
        if not carpetas:
            return
        ok = 0
        for uid, sub in carpetas.items():
            _asegurar_carpeta(uid, '/', CARPETA)
            _asegurar_carpeta(uid, '/' + CARPETA, sub)
            destino = f'/{CARPETA}/{sub}'
            for ruta_local, nombre in archivos:
                try:
                    if not os.path.isfile(ruta_local):
                        continue
                    ruta_drive = _subir(uid, destino, ruta_local, nombre)
                    if ruta_drive:
                        ok += 1
                        try:
                            from interfaces.api.drive_eventos_api import registrar_vinculo
                            registrar_vinculo(uid, conversacion_id, nombre_chat or os.path.basename(ruta_local), ruta_drive)
                        except Exception as e2:
                            print(f'[drive-chat] vínculo: {e2}')
                except Exception as e:
                    print(f'[drive-chat] usuario {uid} {nombre}: {e}')
        print(f'[drive-chat] conv {conversacion_id}: {ok} reflejos en {len(carpetas)} Drives')
    except Exception as e:
        print(f'[drive-chat] error: {e}')


def reflejar_en_drive(conversacion_id, remitente_id, archivos):
    """archivos: lista de (ruta_local, nombre_original). Dispara y olvida."""
    if not archivos:
        return
    threading.Thread(target=_reflejar, args=(conversacion_id, remitente_id, list(archivos)), daemon=True).start()
