# -*- coding: utf-8 -*-
"""Comprobaciones de salud del Drive para balanceadores y el despliegue sin corte.

- GET /api/almacen/salud → 200 si el proceso responde (no toca la base).
- GET /api/almacen/listo → 200 si la base del almacén contesta; 503 si no o si el nodo
  está en drenaje (existe el archivo de drenaje).

Sin sesión y sin detalle: no dicen versiones ni errores.
"""
import os

from flask import Blueprint, jsonify

bp_salud = Blueprint('salud_balanceador', __name__)

ARCHIVO_DRENAJE = os.getenv('ESCALA_ARCHIVO_DRENAJE_ALMACEN', '/run/maquita-almacen/drenar')
RUTAS = ('/api/almacen/salud', '/api/almacen/listo')


def _sin_cache(respuesta, codigo=200):
    respuesta.headers['Cache-Control'] = 'no-store'
    return respuesta, codigo


@bp_salud.get('/api/almacen/salud')
def salud():
    return _sin_cache(jsonify({'estado': 'vivo'}))


@bp_salud.get('/api/almacen/listo')
def listo():
    if os.path.exists(ARCHIVO_DRENAJE):
        return _sin_cache(jsonify({'estado': 'drenando'}), 503)
    ok = False
    try:
        from almacen_bd import conexion
        with conexion() as con:
            with con.cursor() as cur:
                cur.execute('SELECT 1')
                ok = cur.fetchone()[0] == 1
    except Exception:
        ok = False
    return _sin_cache(jsonify({'estado': 'listo' if ok else 'no_listo'}), 200 if ok else 503)
