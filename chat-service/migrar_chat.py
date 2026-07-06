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
