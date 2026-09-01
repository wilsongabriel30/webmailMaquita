# -*- coding: utf-8 -*-
"""
Capa de Interfaces - PDF Editor
===============================

Contiene los puntos de entrada al módulo:
- API: Blueprint para API REST
- Web: Blueprint para interfaz web
"""

from .api import bp_pdf_api
from .web import bp_pdf_web

__all__ = ['bp_pdf_api', 'bp_pdf_web']
