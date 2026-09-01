# -*- coding: utf-8 -*-
"""
Módulo Editor PDF - FARO Maquita
================================

Editor PDF profesional con arquitectura hexagonal.

Características:
- Visualización y navegación de PDFs
- Edición de texto e imágenes
- Gestión de páginas (rotar, eliminar, reordenar)
- Anotaciones y comentarios
- Formularios PDF
- OCR y búsqueda de texto
- Firmas digitales
- Conversiones de formato
- Control de versiones

Arquitectura:
- Dominio: Entidades, Value Objects, Interfaces de repositorios
- Aplicación: Casos de uso, Servicios, DTOs
- Infraestructura: Persistencia, Adaptadores externos
- Interfaces: API REST, Controladores Web
"""

from flask import Flask
from flask_wtf.csrf import CSRFProtect


def registrar_modulo(app: Flask, csrf: CSRFProtect = None):
    """
    Registra el módulo PDF Editor en la aplicación Flask.

    Args:
        app: Instancia de Flask
        csrf: Instancia de CSRFProtect (opcional)
    """
    from .interfaces.api import (bp_pdf_api, bp_pdf_conversiones, bp_pdf_word,
                             bp_pdf_tablas)
    from .interfaces.web import bp_pdf_web

    # Registrar blueprints
    app.register_blueprint(bp_pdf_api, url_prefix='/api/pdf')
    # Conversiones premium (Word/Excel/PPT, numerar, dividir, desbloquear)
    app.register_blueprint(bp_pdf_conversiones, url_prefix='/api/pdf')
    # Edicion tipo Word (OnlyOffice) de la herramienta "Digitalizar y OCR"
    app.register_blueprint(bp_pdf_word, url_prefix='/api/pdf')
    # Columnas de las tablas, dentro del propio PDF
    app.register_blueprint(bp_pdf_tablas, url_prefix='/api/pdf')
    app.register_blueprint(bp_pdf_web, url_prefix='/herramientas/editor-pdf')

    # Eximir API de CSRF si está configurado
    if csrf:
        csrf.exempt(bp_pdf_api)
        csrf.exempt(bp_pdf_conversiones)
        csrf.exempt(bp_pdf_word)
        csrf.exempt(bp_pdf_tablas)

    app.logger.info('[PDF Editor] Módulo registrado correctamente')


__version__ = '1.0.0'
__author__ = 'FARO Maquita'
