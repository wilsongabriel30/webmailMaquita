# -*- coding: utf-8 -*-
"""
Biblioteca LOCAL de GIF del chat institucional.
================================================
Sustituye al buscador externo (Tenor cerró su API en 2026). Todo vive en la
institución: los archivos en `estaticos/gifs/` y el catálogo en la tabla
`chat_gifs` de la BD del chat. Cero llamadas a terceros.

Endpoints (todos exigen sesión, la valida el before_request del servicio):
    GET    /api/chat/gifs/search?q=texto&limit=30   → busca por etiquetas/título
    GET    /api/chat/gifs/trending?limit=30         → los más usados
    POST   /api/chat/gifs/upload  (multipart: file, titulo, etiquetas)
    POST   /api/chat/gifs/<id>/usar                 → contador de uso
    DELETE /api/chat/gifs/<id>                      → solo quien lo subió
"""
import os
import re
import uuid
from datetime import datetime

import psycopg2
import psycopg2.extras
from flask import Blueprint, jsonify, request, session

bp_gifs = Blueprint('gifs_chat', __name__, url_prefix='/api/chat/gifs')

_BASE = os.path.dirname(os.path.abspath(__file__))
DIR_GIFS = os.path.normpath(os.path.join(_BASE, '..', 'web', 'estaticos', 'gifs'))
URL_GIFS = '/static/gifs'
TAM_MAX = 8 * 1024 * 1024  # 8 MB por GIF
EXT_PERMITIDAS = {'.gif', '.webp'}
MAGIC = (b'GIF87a', b'GIF89a', b'RIFF')  # RIFF....WEBP


def _conexion():
    return psycopg2.connect(os.environ['DATABASE_URL'])


def asegurar_tabla():
    """Crea la tabla e índices si no existen (idempotente, se llama al arrancar)."""
    os.makedirs(DIR_GIFS, exist_ok=True)
    with _conexion() as con, con.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_gifs (
                id          SERIAL PRIMARY KEY,
                archivo     VARCHAR(120) NOT NULL UNIQUE,
                titulo      VARCHAR(150) NOT NULL DEFAULT 'GIF',
                etiquetas   TEXT NOT NULL DEFAULT '',
                subido_por  INTEGER,
                usos        INTEGER NOT NULL DEFAULT 0,
                activo      BOOLEAN NOT NULL DEFAULT TRUE,
                creado_en   TIMESTAMP NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS ix_chat_gifs_usos ON chat_gifs (usos DESC);
        """)


def _usuario_id():
    uid = session.get('usuario_id')
    return int(uid) if uid is not None else None


def _normalizar_etiquetas(texto):
    partes = re.split(r'[,\s;]+', (texto or '').lower())
    return ' '.join(sorted({p.strip() for p in partes if p.strip()}))


def _a_dict(fila):
    return {
        'id': fila['id'],
        'url': f"{URL_GIFS}/{fila['archivo']}",
        'titulo': fila['titulo'],
        'etiquetas': fila['etiquetas'].split(),
        'usos': fila['usos'],
        'propio': fila['subido_por'] == _usuario_id(),
    }


def _limite():
    try:
        return max(1, min(int(request.args.get('limit', 30)), 100))
    except ValueError:
        return 30


@bp_gifs.route('/trending', methods=['GET'])
def trending():
    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("SELECT * FROM chat_gifs WHERE activo ORDER BY usos DESC, creado_en DESC LIMIT %s", (_limite(),))
        filas = cur.fetchall()
    return jsonify({'success': True, 'results': [_a_dict(f) for f in filas]})


@bp_gifs.route('/search', methods=['GET'])
def buscar():
    q = (request.args.get('q') or '').strip().lower()
    if not q:
        return trending()
    palabras = [p for p in re.split(r'\s+', q) if p][:6]
    condiciones = ' AND '.join(['(etiquetas ILIKE %s OR titulo ILIKE %s)'] * len(palabras))
    params = []
    for p in palabras:
        params += [f'%{p}%', f'%{p}%']
    params.append(_limite())
    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute(f"SELECT * FROM chat_gifs WHERE activo AND {condiciones} "
                    f"ORDER BY usos DESC, creado_en DESC LIMIT %s", params)
        filas = cur.fetchall()
    return jsonify({'success': True, 'results': [_a_dict(f) for f in filas]})


@bp_gifs.route('/upload', methods=['POST'])
def subir():
    archivo = request.files.get('file')
    if not archivo or not archivo.filename:
        return jsonify({'success': False, 'mensaje': 'Falta el archivo'}), 400
    ext = os.path.splitext(archivo.filename)[1].lower()
    if ext not in EXT_PERMITIDAS:
        return jsonify({'success': False, 'mensaje': 'Solo se aceptan archivos .gif o .webp'}), 400
    datos = archivo.read()
    if len(datos) > TAM_MAX:
        return jsonify({'success': False, 'mensaje': 'El GIF supera los 8 MB'}), 400
    if not datos.startswith(MAGIC):
        return jsonify({'success': False, 'mensaje': 'El archivo no es un GIF válido'}), 400

    titulo = (request.form.get('titulo') or os.path.splitext(archivo.filename)[0])[:150].strip() or 'GIF'
    etiquetas = _normalizar_etiquetas(request.form.get('etiquetas', '') + ' ' + titulo)
    nombre = f"{datetime.now():%Y%m%d}_{uuid.uuid4().hex[:12]}{ext}"
    os.makedirs(DIR_GIFS, exist_ok=True)
    with open(os.path.join(DIR_GIFS, nombre), 'wb') as f:
        f.write(datos)

    with _conexion() as con, con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("INSERT INTO chat_gifs (archivo, titulo, etiquetas, subido_por) VALUES (%s, %s, %s, %s) RETURNING *",
                    (nombre, titulo, etiquetas, _usuario_id()))
        fila = cur.fetchone()
    return jsonify({'success': True, 'gif': _a_dict(fila)}), 201


@bp_gifs.route('/<int:gif_id>/usar', methods=['POST'])
def usar(gif_id):
    with _conexion() as con, con.cursor() as cur:
        cur.execute("UPDATE chat_gifs SET usos = usos + 1 WHERE id = %s", (gif_id,))
    return jsonify({'success': True})


@bp_gifs.route('/<int:gif_id>', methods=['DELETE'])
def eliminar(gif_id):
    with _conexion() as con, con.cursor() as cur:
        cur.execute("UPDATE chat_gifs SET activo = FALSE WHERE id = %s AND subido_por = %s RETURNING id",
                    (gif_id, _usuario_id()))
        ok = cur.fetchone() is not None
    if not ok:
        return jsonify({'success': False, 'mensaje': 'Solo puedes eliminar los GIF que subiste'}), 403
    return jsonify({'success': True})
