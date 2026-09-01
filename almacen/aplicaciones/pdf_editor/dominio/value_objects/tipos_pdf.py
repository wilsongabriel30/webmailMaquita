# -*- coding: utf-8 -*-
"""
Value Objects: Tipos y constantes del dominio PDF.
"""

from enum import Enum


class EstadoDocumento(str, Enum):
    """Estados posibles de un documento PDF."""
    ACTIVO = 'activo'
    PROCESANDO = 'procesando'
    ERROR = 'error'
    ARCHIVADO = 'archivado'
    ELIMINADO = 'eliminado'


class TipoAnotacion(str, Enum):
    """Tipos de anotaciones en PDF."""
    RESALTADO = 'resaltado'
    SUBRAYADO = 'subrayado'
    TACHADO = 'tachado'
    NOTA_ADHESIVA = 'nota_adhesiva'
    TEXTO_LIBRE = 'texto_libre'
    DIBUJO_LIBRE = 'dibujo_libre'
    LINEA = 'linea'
    FLECHA = 'flecha'
    RECTANGULO = 'rectangulo'
    CIRCULO = 'circulo'
    POLIGONO = 'poligono'
    SELLO = 'sello'
    ENLACE = 'enlace'
    ARCHIVO_ADJUNTO = 'archivo_adjunto'


class EstadoAnotacion(str, Enum):
    """Estados de una anotación."""
    ACTIVO = 'activo'
    RESUELTO = 'resuelto'
    ELIMINADO = 'eliminado'


class TipoCampoFormulario(str, Enum):
    """Tipos de campos de formulario PDF."""
    TEXTO = 'texto'
    TEXTO_MULTILINEA = 'texto_multilinea'
    NUMERO = 'numero'
    FECHA = 'fecha'
    HORA = 'hora'
    EMAIL = 'email'
    TELEFONO = 'telefono'
    CHECKBOX = 'checkbox'
    RADIO = 'radio'
    SELECT = 'select'
    LISTA = 'lista'
    FIRMA = 'firma'
    IMAGEN = 'imagen'
    CODIGO_BARRAS = 'codigo_barras'
    CALCULADO = 'calculado'


class TipoFirma(str, Enum):
    """Tipos de firma digital."""
    VISUAL = 'visual'           # Solo imagen/dibujo
    CERTIFICADA = 'certificada' # Con certificado digital
    PADES = 'pades'             # PAdES - PDF Advanced Electronic Signatures
    TIMESTAMP = 'timestamp'      # Solo sello de tiempo


class FormatoExportacion(str, Enum):
    """Formatos de exportación."""
    PDF = 'pdf'
    PDF_A = 'pdf_a'
    PNG = 'png'
    JPEG = 'jpeg'
    SVG = 'svg'
    DOCX = 'docx'
    HTML = 'html'
    TXT = 'txt'


class TipoSello(str, Enum):
    """Tipos de sellos predefinidos."""
    APROBADO = 'aprobado'
    RECHAZADO = 'rechazado'
    REVISADO = 'revisado'
    CONFIDENCIAL = 'confidencial'
    BORRADOR = 'borrador'
    FINAL = 'final'
    COPIA = 'copia'
    ORIGINAL = 'original'
    ANULADO = 'anulado'
    URGENTE = 'urgente'


class ModoVisualizacion(str, Enum):
    """Modos de visualización del PDF."""
    UNA_PAGINA = 'una_pagina'
    DOS_PAGINAS = 'dos_paginas'
    SCROLL_CONTINUO = 'scroll_continuo'
    MINIATURAS = 'miniaturas'


class CalidadRenderizado(str, Enum):
    """Calidad de renderizado de páginas."""
    BAJA = 'baja'       # 72 DPI
    MEDIA = 'media'     # 150 DPI
    ALTA = 'alta'       # 300 DPI
    MAXIMA = 'maxima'   # 600 DPI


# Constantes de tamaño de página (en puntos, 72 puntos = 1 pulgada)
TAMANOS_PAGINA = {
    'carta': (612, 792),      # 8.5 x 11 pulgadas
    'legal': (612, 1008),     # 8.5 x 14 pulgadas
    'a4': (595, 842),         # 210 x 297 mm
    'a3': (842, 1191),        # 297 x 420 mm
    'a5': (420, 595),         # 148 x 210 mm
    'oficio': (612, 936),     # 8.5 x 13 pulgadas
}


# DPI por calidad de renderizado
DPI_POR_CALIDAD = {
    CalidadRenderizado.BAJA: 72,
    CalidadRenderizado.MEDIA: 150,
    CalidadRenderizado.ALTA: 300,
    CalidadRenderizado.MAXIMA: 600
}


# Colores predefinidos para anotaciones
COLORES_ANOTACION = {
    'amarillo': '#FFFF00',
    'verde': '#00FF00',
    'azul': '#00BFFF',
    'rosa': '#FF69B4',
    'naranja': '#FFA500',
    'rojo': '#FF0000',
    'morado': '#9370DB'
}


# Extensiones de archivo permitidas
EXTENSIONES_PDF = {'.pdf'}
EXTENSIONES_IMAGEN = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp'}
EXTENSIONES_DOCUMENTO = {'.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.odt', '.ods', '.odp'}
EXTENSIONES_CONVERTIBLES = EXTENSIONES_PDF | EXTENSIONES_IMAGEN | EXTENSIONES_DOCUMENTO


# Límites del sistema
MAX_TAMANO_ARCHIVO_MB = 100
MAX_PAGINAS_DOCUMENTO = 5000
MAX_ANOTACIONES_POR_PAGINA = 500
MAX_CAMPOS_FORMULARIO = 1000
