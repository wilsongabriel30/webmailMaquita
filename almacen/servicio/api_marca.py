# -*- coding: utf-8 -*-
"""Marca visible del Drive para las Aplicaciones del Drive (Editor de PDF, Tableros).

- GET /api/almacen/marca → {"drive_name": "..."}: el mismo nombre que pinta el
  explorador (`config_almacen.drive_name()`, perilla `config_kv['drive_name']`).

Sin sesión: lo piden las aplicaciones desde el servidor (sin la cookie del usuario) y
el nombre ya se ve en cualquier página del Drive. No dice nada más.
"""
from flask import Blueprint, jsonify

import config_almacen

bp_marca = Blueprint('marca_drive', __name__)

RUTA = '/api/almacen/marca'


@bp_marca.get(RUTA)
def marca():
    respuesta = jsonify({'drive_name': config_almacen.drive_name()})
    respuesta.headers['Cache-Control'] = 'public, max-age=300'
    return respuesta
