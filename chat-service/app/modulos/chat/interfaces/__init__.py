# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                       CHAT - CAPA DE INTERFACES                              ║
║                     Adaptadores de Entrada al Sistema                        ║
╚══════════════════════════════════════════════════════════════════════════════╝

██████████████████████████████████████████████████████████████████████████████
██  REGLAS PARA ESTA CAPA (APLICA A TODOS LOS MODULOS)                       ██
██████████████████████████████████████████████████████████████████████████████

1. RESPONSABILIDADES:
   - Recibir peticiones del mundo exterior (HTTP, WebSocket, CLI)
   - Validar formato de entrada (no reglas de negocio)
   - Transformar request -> DTO para aplicacion
   - Transformar resultado -> response para cliente
   - Manejar autenticacion y autorizacion basica

2. DEPENDENCIAS PERMITIDAS:
   - aplicacion/ (servicios y casos de uso)
   - dominio/ (value objects para respuestas)
   - infraestructura/ (para inyeccion de dependencias)
   - Flask, SocketIO, y frameworks web

3. DEPENDENCIAS PROHIBIDAS:
   - Logica de negocio directa (debe ir a dominio/)
   - SQL directo (debe ir a infraestructura/)

4. ESTRUCTURA TIPICA:
   interfaces/
   ├── api/          # Controladores REST (@bp.route)
   ├── websocket/    # Manejadores SocketIO (@socketio.on)
   └── web/          # Plantillas Jinja2 y estaticos

5. EJEMPLO DE CONTROLADOR CORRECTO:

   from flask import Blueprint, request, jsonify
   from aplicacion.servicios import ServicioChat

   bp = Blueprint('chat', __name__)

   @bp.route('/mensajes', methods=['POST'])
   def enviar_mensaje():
       # 1. Extraer datos del request
       datos = request.get_json()

       # 2. Llamar al servicio de aplicacion
       resultado = servicio_chat.enviar_mensaje(
           conversacion_id=datos['conversacion_id'],
           contenido=datos['contenido']
       )

       # 3. Transformar y retornar respuesta
       return jsonify(resultado.to_dict()), 201

6. PATRON: ADAPTER (Puerto de Entrada)
   Esta capa es el PUERTO DE ENTRADA del hexagono.
   Traduce protocolos externos al lenguaje del dominio.

██████████████████████████████████████████████████████████████████████████████

Contenido actual:
- api/       : Endpoints REST para chat
- websocket/ : Comunicacion tiempo real SocketIO
- web/       : Templates y archivos estaticos
"""

from .api import bp_chat
from .websocket import crear_socketio_chat, emitir_mensaje_nuevo

__all__ = [
    'bp_chat',
    'crear_socketio_chat',
    'emitir_mensaje_nuevo',
]
