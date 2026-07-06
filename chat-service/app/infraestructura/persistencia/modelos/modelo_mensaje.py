# -*- coding: utf-8 -*-
"""
Modelo Mensaje - BRIDGE LEGACY

NOTA: Este archivo es un bridge de compatibilidad.
El codigo real esta en: modulos/chat/infraestructura/persistencia/modelos/modelo_mensaje.py

Para nuevo codigo, usar:
    from modulos.chat.infraestructura.persistencia.modelos import ModeloMensaje, ModeloMediaMensaje

Autor: Wilson Arguello
Migrado: 2026-01-05
"""

from modulos.chat.infraestructura.persistencia.modelos.modelo_mensaje import (
    ModeloMensaje,
    ModeloMediaMensaje,
    ModeloEstadoMensaje,
)

__all__ = ['ModeloMensaje', 'ModeloMediaMensaje', 'ModeloEstadoMensaje']
