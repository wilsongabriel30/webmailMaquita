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


class _DuenoAjeno(Exception):
    """La tabla existe pero pertenece a otro rol, así que no se le pueden añadir columnas."""

    def __init__(self, tabla, error):
        super().__init__(tabla)
        self.tabla = tabla
        self.error = error


def _explicar_dueno(con, tabla, error):
    """Mensaje claro cuando el ALTER TABLE falla porque la tabla es de otro rol.

    Aviso de Andes (09/09/2026): si el directorio se pobló por otra vía, `usuarios` puede
    pertenecer a un rol distinto del que corre la migración y PostgreSQL responde
    «must be owner of table usuarios», sin decir de quién es ni con quién estamos entrando.
    """
    try:
        rol = con.execute(_text("SELECT current_user")).scalar()
    except Exception:
        rol = "(no se pudo consultar)"
    try:
        dueno = con.execute(
            _text("SELECT tableowner FROM pg_tables WHERE tablename = :t"), {"t": tabla}
        ).scalar() or "(desconocido)"
    except Exception:
        dueno = "(no se pudo consultar)"
    return (
        "\nNo se pudo modificar la tabla «%s»: pertenece a otro rol.\n"
        "  Dueña de la tabla: %s\n"
        "  Rol de la migración: %s\n"
        "QUÉ HACER: dar la tabla al rol que migra y volver a ejecutar:\n"
        "  ALTER TABLE %s OWNER TO %s;\n"
        "Solo cambia el dueño; no toca los datos. Si la guía se siguió al pie, el mismo rol\n"
        "crea todo y esto no ocurre: pasa cuando el directorio se pobló por otra vía.\n"
        "Error original: %s\n" % (tabla, dueno, rol, tabla, rol, error)
    )


anadidas = 0
try:
    with gestor._engine.begin() as _con:
        inspector = _inspect(_con)
        for tabla in Base.metadata.sorted_tables:
            if not inspector.has_table(tabla.name):
                continue
            existentes = [c["name"] for c in inspector.get_columns(tabla.name)]
            modelo = [(c.name, _tipo_sql(c), True) for c in tabla.columns]
            for sentencia in _plan(tabla.name, modelo, existentes):
                print("  +", sentencia)
                try:
                    _con.execute(_text(sentencia))
                except Exception as e:
                    if "must be owner of" not in str(e):
                        raise
                    raise _DuenoAjeno(tabla.name, e)
                anadidas += 1
except _DuenoAjeno as fallo:
    # Fuera del `begin()`: la transacción ya se deshizo, así que hace falta otra conexión
    # para poder preguntar quién es el dueño.
    with gestor._engine.connect() as _con:
        sys.stderr.write(_explicar_dueno(_con, fallo.tabla, fallo.error))
    sys.exit(1)
print("Columnas añadidas: %d" % anadidas)
