# -*- coding: utf-8 -*-
"""
Aplicación del Almacén Maquita.
===============================
Fábrica de la app Flask: registra los módulos de la API bajo el MISMO
prefijo del contrato (/api/nextcloud) para que el explorador de FARO
funcione sin cambios. Cuando el proyecto madure, el prefijo podrá ser
/api/almacen con un alias de compatibilidad.

Dependencias del servicio (política de superficie mínima): flask, gunicorn,
psycopg2 — y nada más. Los bytes en producción los sirve nginx.

Autoría: Equipo de Tecnología Maquita — 2026-07-03
"""
import logging
import sys
import os

# Los módulos del servicio viven juntos en esta carpeta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify

from almacen_bd import asegurar_esquema
from config_almacen import CLAVE_SESION, TAMANO_MAX_SUBIDA


def crear_app_almacen() -> Flask:
    """Construye la aplicación del Almacén lista para gunicorn o pruebas."""
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(name)s %(levelname)s %(message)s')

    app = Flask('almacen_maquita')
    app.secret_key = CLAVE_SESION
    app.config['MAX_CONTENT_LENGTH'] = TAMANO_MAX_SUBIDA

    # Esquema de metadatos (idempotente)
    asegurar_esquema()
    from indice_busqueda import asegurar_esquema_indice
    asegurar_esquema_indice()
    from indice_contenido import asegurar_esquema_contenido
    asegurar_esquema_contenido()

    # API bajo el prefijo del contrato actual
    from api_archivos import bp_archivos
    from api_compartir import bp_compartir
    from api_extras import bp_extras
    from api_admin import bp_admin
    from api_versiones import bp_versiones
    from api_onlyoffice import bp_onlyoffice
    app.register_blueprint(bp_archivos, url_prefix='/api/nextcloud')
    app.register_blueprint(bp_compartir, url_prefix='/api/nextcloud')
    app.register_blueprint(bp_extras, url_prefix='/api/nextcloud')
    app.register_blueprint(bp_admin, url_prefix='/api/nextcloud')
    app.register_blueprint(bp_versiones, url_prefix='/api/nextcloud')
    app.register_blueprint(bp_onlyoffice, url_prefix='/api/nextcloud')

    @app.errorhandler(403)
    def sin_permiso(_error):
        """Acción reservada a usuarios master."""
        return jsonify({'success': False, 'error': 'No autorizado'}), 403

    @app.errorhandler(401)
    def sin_sesion(_error):
        """Sin sesión válida: el explorador redirige al login de FARO."""
        return jsonify({'success': False, 'error': 'Sesión requerida'}), 401

    @app.errorhandler(413)
    def demasiado_grande(_error):
        """Archivo más grande que el límite configurado."""
        return jsonify({'success': False,
                        'error': 'El archivo supera el tamaño máximo permitido'}), 413

    @app.errorhandler(500)
    def error_interno(_error):
        return jsonify({'success': False, 'error': 'Error interno del Almacén'}), 500

    app.logger.info('Almacén Maquita listo (contrato /api/nextcloud)')
    return app


if __name__ == '__main__':
    # Arranque directo solo para desarrollo local; producción usa gunicorn
    crear_app_almacen().run(host='127.0.0.1', port=5090, debug=False)
