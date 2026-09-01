# -*- coding: utf-8 -*-
"""
API REST - PDF Editor.

Blueprint para endpoints de la API.
"""

from .pdf_editor_api import bp_pdf_api
from .pdf_conversiones_api import bp_pdf_conversiones
from .pdf_word_api import bp_pdf_word
from .pdf_tablas_api import bp_pdf_tablas
# Registra las rutas de certificados de firma por usuario en bp_pdf_api
from . import firma_certificados_api  # noqa: F401

__all__ = ['bp_pdf_api', 'bp_pdf_conversiones', 'bp_pdf_word',
           'bp_pdf_tablas']
