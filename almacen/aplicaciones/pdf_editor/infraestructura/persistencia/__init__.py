# -*- coding: utf-8 -*-
"""
Persistencia - PDF Editor.

Implementaciones de repositorios con SQLAlchemy/PostgreSQL.
"""

from .repositorio_documento_postgresql import RepositorioDocumentoPostgreSQL

__all__ = ['RepositorioDocumentoPostgreSQL']
