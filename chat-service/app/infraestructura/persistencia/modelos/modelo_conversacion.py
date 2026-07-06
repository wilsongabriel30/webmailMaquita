# -*- coding: utf-8 -*-
"""
Modelo Conversacion - BRIDGE LEGACY

NOTA: Este archivo es un bridge de compatibilidad.
El codigo real esta en: modulos/chat/infraestructura/persistencia/modelos/modelo_conversacion.py

Para nuevo codigo, usar:
    from modulos.chat.infraestructura.persistencia.modelos import ModeloConversacion, ModeloParticipante

Autor: Wilson Arguello
Migrado: 2026-01-05
"""

from modulos.chat.infraestructura.persistencia.modelos.modelo_conversacion import (
    ModeloConversacion,
    ModeloParticipante,
)

__all__ = ['ModeloConversacion', 'ModeloParticipante']
