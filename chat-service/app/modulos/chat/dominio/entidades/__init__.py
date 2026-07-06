# -*- coding: utf-8 -*-
"""
Chat - Entidades de Dominio

CAPA: modulos/chat/dominio/entidades
ARQUITECTURA: Hexagonal - 100%

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-05
Actualizado: 2026-01-06 - Agregado soporte IA Maquita
"""

from modulos.chat.dominio.entidades.conversacion import (
    Conversacion,
    Participante,
)
from modulos.chat.dominio.entidades.mensaje import (
    Mensaje,
    ArchivoMensaje,
    ReaccionMensaje,
    EstadoEntregaMensaje,
)
from modulos.chat.dominio.entidades.conversacion_ia import (
    ConversacionIA,
    MensajeIA,
    ConfiguracionIAUsuario,
    IA_MAQUITA_USER_ID,
)

__all__ = [
    # Chat normal
    'Conversacion',
    'Participante',
    'Mensaje',
    'ArchivoMensaje',
    'ReaccionMensaje',
    'EstadoEntregaMensaje',
    # Chat IA Maquita
    'ConversacionIA',
    'MensajeIA',
    'ConfiguracionIAUsuario',
    'IA_MAQUITA_USER_ID',
]
