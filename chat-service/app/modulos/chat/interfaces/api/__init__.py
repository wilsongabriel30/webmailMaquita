# -*- coding: utf-8 -*-
"""
Chat - API REST

Endpoints HTTP para el chat institucional.
"""

# Por ahora importamos desde la ubicacion legacy para compatibilidad
# TODO: Mover el controlador aqui
from interfaces.api.controlador_chat import bp_chat

__all__ = ['bp_chat']
