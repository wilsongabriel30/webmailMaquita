# -*- coding: utf-8 -*-
"""
Modelo Presencia - BRIDGE LEGACY

NOTA: Este archivo es un bridge de compatibilidad.
El codigo real esta en: modulos/chat/infraestructura/persistencia/modelos/modelo_presencia.py

Para nuevo codigo, usar:
    from modulos.chat.infraestructura.persistencia.modelos import ModeloPresencia, ModeloBloqueo

Autor: Wilson Arguello
Migrado: 2026-01-05
"""

from modulos.chat.infraestructura.persistencia.modelos.modelo_presencia import (
    ModeloPresencia,
    ModeloBloqueo,
)

__all__ = ['ModeloPresencia', 'ModeloBloqueo']
