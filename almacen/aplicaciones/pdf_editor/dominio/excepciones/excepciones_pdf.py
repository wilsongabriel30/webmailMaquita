# -*- coding: utf-8 -*-
"""
Excepciones específicas del dominio PDF Editor.
"""


class PDFEditorError(Exception):
    """Excepción base para errores del editor PDF."""

    def __init__(self, mensaje: str, codigo: str = None, detalles: dict = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo or 'PDF_ERROR'
        self.detalles = detalles or {}

    def to_dict(self) -> dict:
        """Convierte la excepción a diccionario para respuestas API."""
        return {
            'error': True,
            'codigo': self.codigo,
            'mensaje': self.mensaje,
            'detalles': self.detalles
        }


class DocumentoNoEncontrado(PDFEditorError):
    """El documento solicitado no existe."""

    def __init__(self, documento_id: int = None, mensaje: str = None):
        super().__init__(
            mensaje=mensaje or f"Documento no encontrado: {documento_id}",
            codigo='DOCUMENTO_NO_ENCONTRADO',
            detalles={'documento_id': documento_id}
        )


class DocumentoInvalido(PDFEditorError):
    """El documento no es un PDF válido o está corrupto."""

    def __init__(self, mensaje: str = None, razon: str = None):
        super().__init__(
            mensaje=mensaje or "El archivo no es un PDF válido",
            codigo='DOCUMENTO_INVALIDO',
            detalles={'razon': razon}
        )


class PaginaNoEncontrada(PDFEditorError):
    """La página solicitada no existe en el documento."""

    def __init__(self, documento_id: int, pagina: int, total_paginas: int = None):
        mensaje = f"Página {pagina} no encontrada en documento {documento_id}"
        if total_paginas:
            mensaje += f" (total: {total_paginas})"

        super().__init__(
            mensaje=mensaje,
            codigo='PAGINA_NO_ENCONTRADA',
            detalles={
                'documento_id': documento_id,
                'pagina': pagina,
                'total_paginas': total_paginas
            }
        )


class PermisoInsuficiente(PDFEditorError):
    """El usuario no tiene permiso para realizar la operación."""

    def __init__(self, operacion: str, documento_id: int = None, usuario_id: int = None):
        super().__init__(
            mensaje=f"Permiso insuficiente para: {operacion}",
            codigo='PERMISO_INSUFICIENTE',
            detalles={
                'operacion': operacion,
                'documento_id': documento_id,
                'usuario_id': usuario_id
            }
        )


class ArchivoMuyGrande(PDFEditorError):
    """El archivo excede el tamaño máximo permitido."""

    def __init__(self, tamano_mb: float, maximo_mb: float):
        super().__init__(
            mensaje=f"Archivo muy grande: {tamano_mb:.1f}MB (máximo: {maximo_mb}MB)",
            codigo='ARCHIVO_MUY_GRANDE',
            detalles={
                'tamano_mb': tamano_mb,
                'maximo_mb': maximo_mb
            }
        )


class FormatoNoSoportado(PDFEditorError):
    """El formato de archivo no es soportado."""

    def __init__(self, extension: str, formatos_validos: list = None):
        super().__init__(
            mensaje=f"Formato no soportado: {extension}",
            codigo='FORMATO_NO_SOPORTADO',
            detalles={
                'extension': extension,
                'formatos_validos': formatos_validos or ['.pdf']
            }
        )


class OCRError(PDFEditorError):
    """Error durante el procesamiento OCR."""

    def __init__(self, mensaje: str, pagina: int = None, error_original: str = None):
        super().__init__(
            mensaje=mensaje,
            codigo='OCR_ERROR',
            detalles={
                'pagina': pagina,
                'error_original': error_original
            }
        )


class FirmaError(PDFEditorError):
    """Error relacionado con firmas digitales."""

    def __init__(self, mensaje: str, tipo_firma: str = None, error_original: str = None):
        super().__init__(
            mensaje=mensaje,
            codigo='FIRMA_ERROR',
            detalles={
                'tipo_firma': tipo_firma,
                'error_original': error_original
            }
        )


class FormularioError(PDFEditorError):
    """Error en operaciones de formulario."""

    def __init__(self, mensaje: str, campo: str = None, errores_validacion: list = None):
        super().__init__(
            mensaje=mensaje,
            codigo='FORMULARIO_ERROR',
            detalles={
                'campo': campo,
                'errores_validacion': errores_validacion
            }
        )


class VersionError(PDFEditorError):
    """Error en control de versiones."""

    def __init__(self, mensaje: str, documento_id: int = None, version: int = None):
        super().__init__(
            mensaje=mensaje,
            codigo='VERSION_ERROR',
            detalles={
                'documento_id': documento_id,
                'version': version
            }
        )


class ConversionError(PDFEditorError):
    """Error durante la conversión de formatos."""

    def __init__(self, mensaje: str, formato_origen: str = None, formato_destino: str = None):
        super().__init__(
            mensaje=mensaje,
            codigo='CONVERSION_ERROR',
            detalles={
                'formato_origen': formato_origen,
                'formato_destino': formato_destino
            }
        )


class RenderError(PDFEditorError):
    """Error al renderizar una página."""

    def __init__(self, mensaje: str, pagina: int = None, resolucion: str = None):
        super().__init__(
            mensaje=mensaje,
            codigo='RENDER_ERROR',
            detalles={
                'pagina': pagina,
                'resolucion': resolucion
            }
        )
