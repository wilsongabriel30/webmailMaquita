# -*- coding: utf-8 -*-
"""
Capa de Infraestructura - PDF Editor
====================================

Implementaciones concretas de los puertos definidos en el dominio:
- Persistencia: Repositorios PostgreSQL con SQLAlchemy
- Externos: Adaptadores de librerías PDF (PyMuPDF, PyPDF2, etc.)
- Almacenamiento: Gestión de archivos
"""

from .externos.cliente_pymupdf import ClientePyMuPDF

__all__ = ['ClientePyMuPDF']
