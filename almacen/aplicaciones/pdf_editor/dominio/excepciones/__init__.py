# -*- coding: utf-8 -*-
"""
Excepciones del dominio PDF Editor.
"""

from .excepciones_pdf import (
    PDFEditorError,
    DocumentoNoEncontrado,
    DocumentoInvalido,
    PaginaNoEncontrada,
    PermisoInsuficiente,
    ArchivoMuyGrande,
    FormatoNoSoportado,
    OCRError,
    FirmaError,
    FormularioError,
    VersionError,
    ConversionError,
    RenderError
)

__all__ = [
    'PDFEditorError',
    'DocumentoNoEncontrado',
    'DocumentoInvalido',
    'PaginaNoEncontrada',
    'PermisoInsuficiente',
    'ArchivoMuyGrande',
    'FormatoNoSoportado',
    'OCRError',
    'FirmaError',
    'FormularioError',
    'VersionError',
    'ConversionError',
    'RenderError'
]
