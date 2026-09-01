# -*- coding: utf-8 -*-
"""
Capa de Aplicación - PDF Editor
===============================

Contiene los casos de uso, servicios de aplicación y DTOs.
Orquesta la lógica de dominio sin contener lógica de negocio.
"""

from .servicios.servicio_pdf import ServicioPDF

__all__ = ['ServicioPDF']
