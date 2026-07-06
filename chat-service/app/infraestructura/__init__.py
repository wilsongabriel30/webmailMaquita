# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    ⚠️  CARPETA LEGACY - EN MIGRACION  ⚠️                      ║
║                      CAPA DE INFRAESTRUCTURA GLOBAL                          ║
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
│  Usar la estructura modular en modulos/<nombre_modulo>/infraestructura/     │
│                                                                             │
│  Ejemplo para chat:                                                         │
│  from modulos.chat.infraestructura import RepositorioMensajePostgreSQL      │
│  from modulos.chat.infraestructura.cache import CacheMensajesRedis          │
└─────────────────────────────────────────────────────────────────────────────┘

██████████████████████████████████████████████████████████████████████████████
██  NUEVA ESTRUCTURA (usar esta)                                             ██
██████████████████████████████████████████████████████████████████████████████

modulos/
├── chat/
│   └── infraestructura/
│       ├── persistencia/   # Repositorios PostgreSQL
│       ├── cache/          # Implementaciones Redis
│       └── externos/       # APIs de terceros
├── autenticacion/
│   └── infraestructura/
│       └── ...
└── usuarios/
    └── infraestructura/
        └── ...

██████████████████████████████████████████████████████████████████████████████
██  REGLAS DE INFRAESTRUCTURA (aplican en cualquier ubicacion)               ██
██████████████████████████████████████████████████████████████████████████████

1. RESPONSABILIDADES:
   - Implementar interfaces de dominio/repositorios/
   - Conectar con tecnologias externas
   - Traducir entre modelos de dominio y persistencia

2. DEPENDENCIAS PERMITIDAS:
   - dominio/ (interfaces y entidades)
   - SQLAlchemy, Redis, requests, etc.

3. DEPENDENCIAS PROHIBIDAS:
   - Flask (va en interfaces/)
   - aplicacion/ (no debe conocer casos de uso)

Autor: Wilson Arguello
Correo: gestiontecnologia@maquita.com.ec
Fecha: 2026-01-02
"""
