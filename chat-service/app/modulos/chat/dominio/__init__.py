# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                      CHAT - CAPA DE DOMINIO                                  ║
║                    El CORAZON del modulo de chat                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

██████████████████████████████████████████████████████████████████████████████
██  REGLAS ESTRICTAS PARA ESTA CAPA                                          ██
██████████████████████████████████████████████████████████████████████████████

1. SIN DEPENDENCIAS EXTERNAS:
   - NO Flask, NO SQLAlchemy, NO Redis, NO requests
   - SOLO Python puro + dataclasses + typing + uuid + datetime

2. ESTA CAPA DEFINE:
   - Entidades: Objetos con identidad (Conversacion, Mensaje, Participante)
   - Value Objects: Objetos inmutables (TipoMensaje, Constantes)
   - Repositorios: INTERFACES (ABC), no implementaciones

3. VALIDACIONES DE NEGOCIO AQUI:
   - Limites de caracteres en mensajes
   - Cantidad maxima de participantes
   - Tiempos para editar/eliminar mensajes

4. EJEMPLO DE LO QUE NO DEBE ESTAR AQUI:
   # PROHIBIDO en dominio/
   from flask import session          # NO - framework web
   from sqlalchemy import Column      # NO - ORM
   from redis import Redis            # NO - cache

██████████████████████████████████████████████████████████████████████████████

Contenido:
- entidades/     : Conversacion, Mensaje, Participante, Archivo, Reaccion
- repositorios/  : Interfaces abstractas de persistencia
- value_objects/ : Enums, constantes, tipos inmutables
"""

from modulos.chat.dominio.entidades import (
    Conversacion, Participante, Mensaje, ArchivoMensaje, ReaccionMensaje, EstadoEntregaMensaje
)
from modulos.chat.dominio.value_objects import (
    TipoConversacion, TipoMensaje, TipoMedia, RolParticipante,
    EstadoMensaje, AccionUsuario, ConstantesChat, EstadoPresencia,
    ContenidoMensaje, InfoArchivo, IndicadorEscritura, PresenciaUsuario,
    UbicacionMensaje, ContactoMensaje
)
from modulos.chat.dominio.repositorios import (
    RepositorioConversacion, RepositorioParticipante, RepositorioMensaje,
    RepositorioArchivoMensaje, RepositorioReaccion, RepositorioPresencia,
    RepositorioBloqueo, RepositorioIndicadorAccion
)

__all__ = [
    # Entidades
    'Conversacion', 'Participante', 'Mensaje', 'ArchivoMensaje', 'ReaccionMensaje', 'EstadoEntregaMensaje',
    # Value Objects
    'TipoConversacion', 'TipoMensaje', 'TipoMedia', 'RolParticipante',
    'EstadoMensaje', 'AccionUsuario', 'ConstantesChat', 'EstadoPresencia',
    'ContenidoMensaje', 'InfoArchivo', 'IndicadorEscritura', 'PresenciaUsuario',
    'UbicacionMensaje', 'ContactoMensaje',
    # Repositorios (Interfaces)
    'RepositorioConversacion', 'RepositorioParticipante', 'RepositorioMensaje',
    'RepositorioArchivoMensaje', 'RepositorioReaccion', 'RepositorioPresencia',
    'RepositorioBloqueo', 'RepositorioIndicadorAccion',
]
