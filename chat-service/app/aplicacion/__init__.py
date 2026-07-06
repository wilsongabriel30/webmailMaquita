# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    ⚠️  CARPETA LEGACY - EN MIGRACION  ⚠️                      ║
║                        CAPA DE APLICACION GLOBAL                             ║
╚══════════════════════════════════════════════════════════════════════════════╝

██████████████████████████████████████████████████████████████████████████████
██  ⚠️  AVISO IMPORTANTE DE MIGRACION                                        ██
██████████████████████████████████████████████████████████████████████████████

Esta carpeta contiene codigo LEGACY que esta siendo migrado a la nueva
estructura modular (Vertical Slicing).

┌─────────────────────────────────────────────────────────────────────────────┐
│  PARA CODIGO NUEVO:                                                         │
│  ─────────────────                                                          │
│  NO crear nuevos archivos aqui.                                             │
│  Usar la estructura modular en modulos/<nombre_modulo>/aplicacion/          │
│                                                                             │
│  Ejemplo para chat:                                                         │
│  from modulos.chat.aplicacion import ServicioChat                           │
│  from modulos.chat.aplicacion.casos_uso import EnviarMensaje                │
└─────────────────────────────────────────────────────────────────────────────┘

██████████████████████████████████████████████████████████████████████████████
██  NUEVA ESTRUCTURA (usar esta)                                             ██
██████████████████████████████████████████████████████████████████████████████

modulos/
├── chat/
│   └── aplicacion/
│       ├── servicios/    # ServicioChat (orquestador)
│       ├── casos_uso/    # Casos de uso especificos
│       └── dtos/         # Data Transfer Objects
├── autenticacion/
│   └── aplicacion/
│       └── ...
└── usuarios/
    └── aplicacion/
        └── ...

██████████████████████████████████████████████████████████████████████████████
██  REGLAS DE APLICACION (aplican en cualquier ubicacion)                    ██
██████████████████████████████████████████████████████████████████████████████

1. DEPENDENCIAS PERMITIDAS:
   - dominio/ (entidades, repositorios, value objects)
   - Python estandar

2. DEPENDENCIAS PROHIBIDAS:
   - Flask, SQLAlchemy (eso va en infraestructura/)
   - Imports de interfaces/

3. RESPONSABILIDADES:
   - Coordinar operaciones de dominio
   - Gestionar transacciones
   - Emitir eventos de dominio

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
"""
