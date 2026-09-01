# -*- coding: utf-8 -*-
"""
Capa de Dominio - Editor PDF
============================

Contiene la lógica de negocio pura del editor PDF:
- Entidades: DocumentoPDF, Pagina, Anotacion, Formulario, Firma, Version
- Value Objects: Tipos, Coordenadas, Permisos
- Repositorios: Interfaces (puertos) para persistencia
- Servicios de dominio: Lógica de negocio compleja
- Excepciones: Errores específicos del dominio
"""

from .entidades.documento_pdf import DocumentoPDF
from .entidades.pagina import Pagina
from .value_objects.tipos_pdf import EstadoDocumento, TipoAnotacion

__all__ = [
    'DocumentoPDF',
    'Pagina',
    'EstadoDocumento',
    'TipoAnotacion'
]
