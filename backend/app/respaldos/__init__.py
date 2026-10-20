"""T-74 · Alta automática de equipos en UrBackup desde Teams Maquita (20/10/2026).

Dos pasos para que la clave del cliente UrBackup nunca viaje con la sesión de la persona:
    POST /api/respaldos/alta-equipo   con la sesión del trabajador → código de un solo uso (10 min)
    POST /api/respaldos/canjear       sin sesión (tarea de la app como SISTEMA) → servidor, puerto y clave

Módulos: esquema (tablas), vinculos (quién es dueño de qué cliente), codigos (código de un solo uso),
urbackup_api (panel de UrBackup con un usuario propio), limites (intentos), router (endpoints).
"""
