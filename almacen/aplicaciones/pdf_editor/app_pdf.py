"""Punto de entrada de la app autónoma del Editor de PDF — Aplicación del Drive Maquita.

Monta el editor como una app Flask independiente: su propia configuración
(`config.py`), autenticación por el token del Drive (`auth_drive.py`) y el módulo del
editor (`registrar_modulo`, en `__init__.py`). No necesita Raíces.

Arranque:
    export $(grep -v '^#' .env | xargs)      # o usa un EnvironmentFile del servicio
    python app_pdf.py                          # dev
    gunicorn 'app_pdf:app' --bind 0.0.0.0:8790 # producción
"""
import os
import sys

# El módulo del editor usa imports relativos (paquete) y `from config import Config`
# (nivel superior). Para que ambos resuelvan, dejamos en el path el directorio padre
# (para `import pdf_editor`) y este directorio (para `config`/`auth_drive`).
_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
for _p in (_PARENT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from flask import Flask, redirect
from flask_wtf.csrf import CSRFProtect

from config import Config
import auth_drive
import pdf_editor  # el paquete de este directorio (registrar_modulo en __init__)


def crear_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.secret_key = Config.SECRET_KEY or "cambia-esto-en-produccion"

    csrf = CSRFProtect(app)
    auth_drive.init_auth(app)

    # Monta /api/pdf/* y /herramientas/editor-pdf/*
    pdf_editor.registrar_modulo(app, csrf)

    @app.route("/")
    def _inicio():
        return redirect("/herramientas/editor-pdf/")

    _crear_tablas()
    return app



def _crear_tablas():
    """Crea las tablas del editor en la BD 'herramientas' si no existen."""
    try:
        from config import Config
        if not Config.HERRAMIENTAS_DATABASE_URI:
            return
        from sqlalchemy import create_engine
        eng = create_engine(Config.HERRAMIENTAS_DATABASE_URI)
        # importar los modelos registra sus tablas en el Base comun
        from pdf_editor.infraestructura.persistencia.modelos import (
            modelo_documento, modelo_anotacion, modelo_version)  # noqa: F401
        from pdf_editor.infraestructura.persistencia.modelos.base_orm import Base
        Base.metadata.create_all(eng)
    except Exception as _e:
        import logging
        logging.getLogger(__name__).warning("Tablas del editor no creadas: %s", _e)


app = crear_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8790")))
