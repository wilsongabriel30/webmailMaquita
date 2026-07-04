# -*- coding: utf-8 -*-
"""
Autenticación del Almacén con la sesión del WEBMAIL Maquita.
============================================================
El backend del webmail (FastAPI) emite un JWT HS256 en la cookie httpOnly
`access_token` (payload: sub=<usuario del buzón>, type=access). Como el
Almacén se sirve bajo el MISMO dominio, esa cookie llega sola en cada
petición: aquí se valida con el MISMO secreto (`WEBMAIL_SECRET_KEY`, el
`SECRET_KEY` del backend del webmail) y se resuelve el id numérico del
usuario en la tabla `usuarios` de la BD del Almacén (se crea sola la
primera vez que el usuario entra).

Sin FARO ni nómina: la tabla `usuarios` local cumple el papel del
directorio (las búsquedas de "compartir con..." consultan ahí) y
`trabajadores` existe VACÍA solo para que los LEFT JOIN del motor
funcionen sin cambios. `NOMINA_DB_*` debe apuntar a la MISMA BD del
Almacén (app_webmail lo hace solo si no se define otra cosa).

Administradores: la variable `ALMACEN_ADMINS` (usuarios separados por coma,
ej. "admin@dominio.org,ti@dominio.org") define quién tiene rol master
(recuperación de archivos ajenos, cuotas, retención).
"""
import logging
import os

import jwt
from flask import request

from almacen_bd import consultar, ejecutar

log = logging.getLogger('almacen.auth_webmail')

_SECRETO = os.getenv('WEBMAIL_SECRET_KEY', '')
_ADMINS = {u.strip().lower() for u in os.getenv('ALMACEN_ADMINS', '').split(',') if u.strip()}
_REDIS_URL = os.getenv('ALMACEN_REDIS_URL', '')  # opcional: valida sesión viva (logout)

_cache_usuarios: dict = {}   # username -> (id, role)
_redis_cliente = None


def asegurar_tablas_webmail() -> None:
    """Crea el directorio local de usuarios (idempotente). `trabajadores`
    existe vacía únicamente para satisfacer los LEFT JOIN del motor."""
    ejecutar("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            full_name TEXT,
            role TEXT NOT NULL DEFAULT 'user',
            active BOOLEAN NOT NULL DEFAULT TRUE,
            trabajador_id INTEGER,
            creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    ejecutar("""
        CREATE TABLE IF NOT EXISTS trabajadores (
            id INTEGER PRIMARY KEY,
            nombres TEXT,
            apellidos TEXT
        );
    """)


def _sesion_viva(username: str) -> bool:
    """Si hay Redis configurado, exige que la sesión del webmail siga activa
    (el logout borra `imap_pass:<usuario>`). Sin Redis, basta el JWT."""
    global _redis_cliente
    if not _REDIS_URL:
        return True
    try:
        if _redis_cliente is None:
            import redis
            _redis_cliente = redis.Redis.from_url(_REDIS_URL, socket_timeout=2)
        return bool(_redis_cliente.exists(f'imap_pass:{username}'))
    except Exception as excepcion:
        log.warning('Redis no disponible para validar sesión (%s); se rechaza', excepcion)
        return False


def usuario_webmail() -> tuple:
    """Valida la cookie del webmail. Devuelve (usuario_id, role) o (None, None)."""
    if not _SECRETO:
        log.error('WEBMAIL_SECRET_KEY no configurado: nadie puede autenticarse')
        return None, None
    token = request.cookies.get('access_token')
    if not token:
        return None, None
    try:
        payload = jwt.decode(token, _SECRETO, algorithms=['HS256'])
    except jwt.PyJWTError:
        return None, None
    if payload.get('type') != 'access':
        return None, None
    username = (payload.get('sub') or '').strip().lower()
    if not username or not _sesion_viva(username):
        return None, None
    return _obtener_o_crear(username)


def _obtener_o_crear(username: str) -> tuple:
    """Id numérico y rol del usuario en el directorio local; lo crea si no existe.
    El rol se sincroniza con ALMACEN_ADMINS en cada arranque (caché por proceso)."""
    if username in _cache_usuarios:
        return _cache_usuarios[username]
    rol_esperado = 'master' if username in _ADMINS else 'user'
    filas = consultar('SELECT id, role, active FROM usuarios WHERE username = %s', (username,))
    if filas:
        if not filas[0]['active']:
            return None, None
        uid, rol = filas[0]['id'], filas[0]['role']
        if rol != rol_esperado:
            ejecutar('UPDATE usuarios SET role = %s WHERE id = %s', (rol_esperado, uid))
            rol = rol_esperado
    else:
        ejecutar("""
            INSERT INTO usuarios (username, full_name, role)
            VALUES (%s, %s, %s) ON CONFLICT (username) DO NOTHING
        """, (username, username.split('@')[0].replace('.', ' ').title(), rol_esperado))
        filas = consultar('SELECT id, role FROM usuarios WHERE username = %s', (username,))
        if not filas:
            return None, None
        uid, rol = filas[0]['id'], filas[0]['role']
    _cache_usuarios[username] = (uid, rol)
    return uid, rol
