# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     CHAT - CAPA DE APLICACION                                ║
║                   Orquestacion y Casos de Uso                                ║
╚══════════════════════════════════════════════════════════════════════════════╝

██████████████████████████████████████████████████████████████████████████████
██  REGLAS PARA ESTA CAPA                                                    ██
██████████████████████████████████████████████████████████████████████████████

1. DEPENDENCIAS PERMITIDAS:
   - dominio/ (entidades, repositorios, value objects)
   - Python estandar

2. DEPENDENCIAS PROHIBIDAS:
   - Flask, SQLAlchemy (eso va en infraestructura/)
   - Imports de interfaces/ (no al reves)

3. RESPONSABILIDADES:
   - Coordinar operaciones de dominio
   - Gestionar transacciones (inicio/fin)
   - Validar reglas de aplicacion (no de negocio)
   - Emitir eventos de dominio

4. EJEMPLO DE SERVICIO CORRECTO:

   class ServicioChat:
       def __init__(self, repo_mensaje: RepositorioMensaje):  # Interfaz!
           self._repo = repo_mensaje

       def enviar_mensaje(self, ...):
           # Coordinar operaciones
           mensaje = Mensaje.crear_texto(...)  # Usa dominio
           return self._repo.crear(mensaje)    # Usa interfaz

██████████████████████████████████████████████████████████████████████████████

Contenido:
- servicios/  : ServicioChat (orquestador principal)
- casos_uso/  : Casos de uso especificos
- dtos/       : Data Transfer Objects
"""

from .servicios import ServicioChat

__all__ = ['ServicioChat']
