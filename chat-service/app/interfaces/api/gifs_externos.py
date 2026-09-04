# -*- coding: utf-8 -*-
"""
GIF: fuentes EXTERNAS como segunda opción (28/08/2026).
=======================================================
Primero se busca en la biblioteca propia (controlador_gifs.py). Si no está lo que
la persona busca, puede pedir «Buscar en fuentes externas»: se consulta a los
proveedores configurados y, al elegir uno, el GIF SE DESCARGA a nuestra
infraestructura (estaticos/gifs + tabla chat_gifs) y el mensaje sale con la copia
local. Así la biblioteca crece con lo que la gente realmente usa y nunca
dependemos del tercero para mostrar el historial.

Fuentes:
    - giphy   → requiere GIPHY_API_KEY en .env (si no hay, se usa la clave pública
                de pruebas de GIPHY, con límite de peticiones; conviene una propia).
    - commons → Wikimedia Commons (licencias libres), sin clave.
    - Tenor cerró su API en 2026 (403 «Tenor API is discontinued»).

Endpoints (sesión obligatoria, la valida el before_request del servicio):
    GET  /api/chat/gifs/externos?q=texto&limit=24
    POST /api/chat/gifs/externos/importar  {fuente, id, url, titulo, etiquetas}
"""
import os
import re
import uuid
import logging
from datetime import datetime
from urllib.parse import quote

import psycopg2
import psycopg2.extras
import requests
from flask import jsonify, request

from interfaces.api.controlador_gifs import (bp_gifs, DIR_GIFS, MAGIC, TAM_MAX, _a_dict, _conexion,
                                             _normalizar_etiquetas, _usuario_id)

logger = logging.getLogger(__name__)
GIPHY_KEY = os.getenv('GIPHY_API_KEY') or 'GlVGYHkr3WSBnllca54iNt0yFbjz7L65'  # clave pública de pruebas de GIPHY
UA = {'User-Agent': 'RaicesMaquitaChat/1.0 (https://maquita.com.ec)'}
TIEMPO = 12


def buscar_giphy(q, limite=24, offset=0):
    r = requests.get('https://api.giphy.com/v1/gifs/search', timeout=TIEMPO, headers=UA,
                     params={'api_key': GIPHY_KEY, 'q': q, 'limit': limite, 'offset': offset, 'lang': 'es', 'rating': 'pg'})
    if r.status_code == 429:
        raise RuntimeError('GIPHY: límite de peticiones alcanzado, intenta más tarde')
    r.raise_for_status()
    res = []
    for g in r.json().get('data', []):
        im = g.get('images', {})
        desc = im.get('downsized') or im.get('original') or {}
        vista = im.get('fixed_width_small') or im.get('fixed_width') or desc
        if not desc.get('url'):
            continue
        res.append({'fuente': 'giphy', 'id': g['id'], 'titulo': (g.get('title') or 'GIF')[:150],
                    'url_vista': vista.get('url'), 'url': desc['url'], 'bytes': int(desc.get('size') or 0)})
    return res


def buscar_commons(q, limite=24):
    r = requests.get('https://commons.wikimedia.org/w/api.php', timeout=TIEMPO, headers=UA, params={
        'action': 'query', 'generator': 'search', 'gsrsearch': f'{q} filemime:image/gif', 'gsrnamespace': 6,
        'gsrlimit': limite, 'prop': 'imageinfo', 'iiprop': 'url|size|mime', 'iiurlwidth': 200, 'format': 'json'})
    r.raise_for_status()
    res = []
    for p in (r.json().get('query', {}).get('pages') or {}).values():
        ii = (p.get('imageinfo') or [{}])[0]
        if ii.get('mime') != 'image/gif' or not ii.get('url'):
            continue
        titulo = re.sub(r'^File:|\.gif$', '', p.get('title', ''), flags=re.I).replace('_', ' ')
        res.append({'fuente': 'commons', 'id': str(p['pageid']), 'titulo': titulo[:150],
                    'url_vista': ii.get('thumburl') or ii['url'], 'url': ii['url'], 'bytes': int(ii.get('size') or 0)})
    return res


FUENTES = {'giphy': buscar_giphy, 'commons': buscar_commons}


@bp_gifs.route('/externos', methods=['GET'])
def externos():
    q = (request.args.get('q') or '').strip()
    if not q:
        return jsonify({'success': False, 'mensaje': 'Falta q'}), 400
    try:
        limite = max(1, min(int(request.args.get('limit', 24)), 50))
    except ValueError:
        limite = 24
    resultados, errores = [], []
    for nombre, fn in FUENTES.items():
        try:
            resultados += fn(q, limite)
        except Exception as e:  # una fuente caída no tumba la búsqueda
            logger.warning(f'GIF externos {nombre}: {e}')
            errores.append(f'{nombre}: {e}')
    # Los que ya tenemos en la biblioteca se marcan (y se devuelven con su copia local)
    urls = [r['url'] for r in resultados]
    locales = {}
    if urls:
        with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute('SELECT * FROM chat_gifs WHERE activo AND origen_url = ANY(%s)', (urls,))
            for f in cur.fetchall():
                locales[f['origen_url']] = _a_dict(f)
    for r in resultados:
        if r['url'] in locales:
            r['local'] = locales[r['url']]
    return jsonify({'success': True, 'results': resultados, 'errores': errores})


def importar_gif(url, titulo, etiquetas, fuente, subido_por=None):
    """Descarga un GIF externo a la biblioteca (una sola vez por origen_url). Devuelve la fila."""
    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute('SELECT * FROM chat_gifs WHERE origen_url = %s', (url,))
        fila = cur.fetchone()
        if fila:
            if not fila['activo']:
                cur.execute('UPDATE chat_gifs SET activo = TRUE WHERE id = %s RETURNING *', (fila['id'],))
                fila = cur.fetchone()
            return fila
    r = requests.get(url, timeout=40, headers=UA, stream=True)
    r.raise_for_status()
    datos = r.raw.read(TAM_MAX + 1, decode_content=True)
    if len(datos) > TAM_MAX:
        raise ValueError('El GIF supera los 8 MB')
    if not datos.startswith(MAGIC):
        raise ValueError('El origen no devolvió un GIF válido')
    ext = '.webp' if datos.startswith(b'RIFF') else '.gif'
    nombre = f"{datetime.now():%Y%m%d}_{uuid.uuid4().hex[:12]}{ext}"
    os.makedirs(DIR_GIFS, exist_ok=True)
    with open(os.path.join(DIR_GIFS, nombre), 'wb') as f:
        f.write(datos)
    titulo = (titulo or 'GIF')[:150]
    etiquetas = _normalizar_etiquetas(f'{etiquetas or ""} {titulo} {fuente}')
    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute('INSERT INTO chat_gifs (archivo, titulo, etiquetas, subido_por, origen_url) VALUES (%s,%s,%s,%s,%s) '
                    'ON CONFLICT (origen_url) WHERE origen_url IS NOT NULL DO UPDATE SET activo = TRUE RETURNING *',
                    (nombre, titulo, etiquetas, subido_por, url))
        return cur.fetchone()


@bp_gifs.route('/externos/importar', methods=['POST'])
def externos_importar():
    d = request.get_json(silent=True) or {}
    url = (d.get('url') or '').strip()
    fuente = d.get('fuente') or 'externo'
    if not re.match(r'^https://([a-z0-9.-]+\.giphy\.com|upload\.wikimedia\.org)/', url):
        return jsonify({'success': False, 'mensaje': 'Origen no permitido'}), 400
    try:
        fila = importar_gif(url, d.get('titulo'), d.get('etiquetas'), fuente, None)  # sin dueño: es de la biblioteca común
    except Exception as e:
        logger.warning(f'GIF importar {url}: {e}')
        return jsonify({'success': False, 'mensaje': f'No se pudo traer el GIF: {e}'}), 502
    return jsonify({'success': True, 'gif': _a_dict(fila)}), 201
