# -*- coding: utf-8 -*-
"""Migración del servicio de chat: crea las tablas de los modelos en su BD.
Idempotente (create_all no recrea lo existente). Uso:
  DATABASE_URL=... venv/bin/python3 migrar_chat.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "shims"))

from compartido.infraestructura.base_datos import Base, obtener_gestor, inicializar_base_datos

# Importar TODOS los modelos del chat para que se registren en Base.metadata
from modulos.usuarios.infraestructura.persistencia.modelos.modelo_usuario import ModeloUsuario  # noqa
from modulos.chat.infraestructura.persistencia.modelos import (  # noqa
    modelo_conversacion, modelo_mensaje, modelo_reaccion,
    modelo_presencia, modelo_indicador, modelo_notificacion,
)

import os as _os
gestor = inicializar_base_datos(_os.environ["DATABASE_URL"])
antes = set(Base.metadata.tables.keys())
print("Tablas del chat a crear/verificar:", sorted(antes))
gestor.crear_tablas()
print(f"OK — {len(antes)} tablas creadas/verificadas en la BD del chat.")

# `create_all` crea las TABLAS que faltan, nunca las COLUMNAS de una tabla que ya existe: una
# columna añadida al modelo más tarde no llegaba a ninguna instalación, y el código que la leía
# tumbaba la petición. Aquí se añaden las que falten. Solo se AÑADE, nunca se borra ni se cambia
# el tipo de nada.
from sqlalchemy import inspect as _inspect, text as _text  # noqa: E402
from columnas_faltantes import plan as _plan  # noqa: E402

_TIPOS = {"BIGINT": "bigint", "INTEGER": "integer", "BOOLEAN": "boolean", "TEXT": "text",
          "DATETIME": "timestamptz", "TIMESTAMP": "timestamptz", "VARCHAR": "text",
          "JSON": "jsonb", "JSONB": "jsonb", "FLOAT": "double precision"}


def _tipo_sql(columna):
    nombre = columna.type.__class__.__name__.upper()
    return _TIPOS.get(nombre, "text")


anadidas = 0
with gestor.motor.begin() as _con:
    inspector = _inspect(_con)
    for tabla in Base.metadata.sorted_tables:
        if not inspector.has_table(tabla.name):
            continue
        existentes = [c["name"] for c in inspector.get_columns(tabla.name)]
        modelo = [(c.name, _tipo_sql(c), True) for c in tabla.columns]
        for sentencia in _plan(tabla.name, modelo, existentes):
            print("  +", sentencia)
            _con.execute(_text(sentencia))
            anadidas += 1
print("Columnas añadidas: %d" % anadidas)
