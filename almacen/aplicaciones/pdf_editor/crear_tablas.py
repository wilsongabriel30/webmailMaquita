"""Crea las tablas del editor en la BD 'herramientas' (una vez, en la instalación).
Evita la condición de carrera de crearlas desde varios workers al arrancar.
"""
import os
import sys

_H = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _H)
sys.path.insert(0, os.path.dirname(_H))

_env = os.path.join(_H, ".env")
if os.path.exists(_env):
    for _l in open(_env, encoding="utf-8"):
        _l = _l.strip()
        if "=" in _l and not _l.startswith("#"):
            _k, _v = _l.split("=", 1)
            os.environ.setdefault(_k, _v)

from config import Config

if not Config.HERRAMIENTAS_DATABASE_URI:
    print("Sin HERRAMIENTAS_DATABASE_URI: no se crean tablas")
    sys.exit(0)

from pdf_editor.infraestructura.persistencia.modelos import (  # noqa: F401
    modelo_documento, modelo_anotacion, modelo_version)
from pdf_editor.infraestructura.persistencia.modelos.base_orm import Base
from sqlalchemy import create_engine

Base.metadata.create_all(create_engine(Config.HERRAMIENTAS_DATABASE_URI))
print("Tablas del editor de PDF creadas/verificadas")
