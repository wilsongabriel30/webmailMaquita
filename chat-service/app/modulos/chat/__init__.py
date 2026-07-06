# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                        MODULO: CHAT INSTITUCIONAL                            ║
║                   Sistema de Mensajeria en Tiempo Real                       ║
╚══════════════════════════════════════════════════════════════════════════════╝

██████████████████████████████████████████████████████████████████████████████
██  COMO IMPORTAR DESDE ESTE MODULO                                          ██
██████████████████████████████████████████████████████████████████████████████

# FORMA RECOMENDADA - Importar desde el modulo raiz:
from modulos.chat import ServicioChat, Conversacion, Mensaje
from modulos.chat import TipoMensaje, TipoConversacion

# FORMA ALTERNATIVA - Importar desde subcapas:
from modulos.chat.dominio import Conversacion, Participante
from modulos.chat.aplicacion import ServicioChat

# NUNCA HACER - No importar implementaciones directamente:
from modulos.chat.infraestructura.persistencia import ...  # PROHIBIDO!

██████████████████████████████████████████████████████████████████████████████
██  ESTRUCTURA DEL MODULO                                                    ██
██████████████████████████████████████████████████████████████████████████████

chat/
├── dominio/           # NUCLEO - Logica de negocio PURA
│   ├── entidades/     # Conversacion, Mensaje, Participante
│   ├── repositorios/  # INTERFACES de persistencia (no implementaciones)
│   └── value_objects/ # TipoMensaje, TipoConversacion, Constantes
│
├── aplicacion/        # ORQUESTACION - Casos de uso
│   ├── servicios/     # ServicioChat (punto de entrada principal)
│   ├── casos_uso/     # Casos de uso especificos
│   └── dtos/          # Objetos de transferencia
│
├── infraestructura/   # TECNICO - Implementaciones concretas
│   ├── persistencia/  # PostgreSQL, modelos SQLAlchemy
│   └── cache/         # Redis (mensajes, presencia, sesiones)
│
└── interfaces/        # ENTRADA - Adaptadores externos
    ├── api/           # Controladores REST
    ├── websocket/     # Manejadores WebSocket
    └── web/           # Plantillas y estaticos

██████████████████████████████████████████████████████████████████████████████
██  REGLA DE ORO: DEPENDENCIAS                                               ██
██████████████████████████████████████████████████████████████████████████████

    interfaces/ ───> aplicacion/ ───> dominio/
         │                │
         └────────────────┴───> infraestructura/

    - dominio/: SIN dependencias externas (ni Flask, ni SQLAlchemy, ni nada)
    - aplicacion/: Solo depende de dominio/
    - infraestructura/: Implementa interfaces de dominio/
    - interfaces/: Puede usar todo

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
"""

# ═══════════════════════════════════════════════════════════════════════════
# EXPORTS PUBLICOS DEL MODULO
# Solo estas clases/funciones deben usarse desde fuera del modulo
# ═══════════════════════════════════════════════════════════════════════════

from .dominio.entidades import Conversacion, Participante, Mensaje, ArchivoMensaje, ReaccionMensaje
from .dominio.value_objects import (
    TipoConversacion, TipoMensaje, TipoMedia, RolParticipante,
    EstadoMensaje, AccionUsuario, ConstantesChat
)
from .aplicacion.servicios import ServicioChat, ServicioCache, ServicioBusqueda
from .dominio.repositorios import FiltrosBusqueda, ResultadoBusqueda

__all__ = [
    # ─── Entidades de Dominio ───
    'Conversacion',
    'Participante',
    'Mensaje',
    'ArchivoMensaje',
    'ReaccionMensaje',
    # ─── Value Objects ───
    'TipoConversacion',
    'TipoMensaje',
    'TipoMedia',
    'RolParticipante',
    'EstadoMensaje',
    'AccionUsuario',
    'ConstantesChat',
    # ─── Servicios de Aplicacion ───
    'ServicioChat',
    'ServicioCache',
    'ServicioBusqueda',
    # ─── DTOs de Busqueda ───
    'FiltrosBusqueda',
    'ResultadoBusqueda',
]
