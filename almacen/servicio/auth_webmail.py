# -*- coding: utf-8 -*-
"""
Autenticación del Almacén con la sesión del WEBMAIL Maquita.
============================================================
El backend del webmail (FastAPI) emite un JWT HS256 en la cookie httpOnly
`access_token` (payload: sub=<usuario del buzón>, type=access). Como el
Almacén se sirve bajo el MISMO dominio, esa cookie llega sola en cada
petición: aquí se valida con el MISMO secreto (`WEBMAIL_SECRET_KEY`, el
`SECRET_KEY` del backend del webmail) y se resuelve el id numérico del
usuario según el MODO DE DIRECTORIO:

- `ALMACEN_MODO_DIRECTORIO=local` (default): el directorio es la tabla
  `usuarios` de la BD del Almacén; el usuario se crea solo la primera vez
  que entra (instalaciones autocontenidas: solo webmail + almacén).
- `ALMACEN_MODO_DIRECTORIO=nomina`: el correo del buzón se busca en la
  columna `email` de la tabla `usuarios` de la BD de NÓMINA (`NOMINA_DB_*`).
  El id resultante es EL MISMO que usa el resto del sistema → una sola
  identidad y UN solo almacén por persona (estilo Microsoft 365: entras al
  correo y tus archivos/OnlyOffice son los mismos en todas partes). Quien
  no está en el directorio no entra (403).

`trabajadores` existe VACÍA en modo local solo para que los LEFT JOIN del
motor funcionen sin cambios.

Control de acceso adicional:
- `ALMACEN_ADMINS`: correos con rol master (recuperación de archivos ajenos,
  cuotas, retención).
- `ALMACEN_PILOTO` (opcional): si se define, SOLO esos correos (más los
  admins) pueden usar el Almacén — útil para fases de prueba. Vacío = todos.
"""
import logging
import os

import jwt
from flask import request

from almacen_bd import consultar, ejecutar

log = logging.getLogger('almacen.auth_webmail')

_SECRETO = os.getenv('WEBMAIL_SECRET_KEY', '')
_MODO = os.getenv('ALMACEN_MODO_DIRECTORIO', 'local').strip().lower()
_ADMINS = {u.strip().lower() for u in os.getenv('ALMACEN_ADMINS', '').split(',') if u.strip()}
_PILOTO = {u.strip().lower() for u in os.getenv('ALMACEN_PILOTO', '').split(',') if u.strip()}
_REDIS_URL = os.getenv('ALMACEN_REDIS_URL', '')  # opcional: valida sesión viva (logout)

_cache_usuarios: dict = {}   # username -> (id, role)
_redis_cliente = None


def asegurar_tablas_webmail() -> None:
    """Modo local: crea el directorio propio (idempotente). En modo nomina el
    directorio es externo y aquí no se crea nada."""
    if _MODO != 'local':
        return
    ejecutar("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            full_name TEXT,
            role TEXT NOT NULL DEFAULT 'user',
            active BOOLEAN NOT NULL DEFAULT TRUE,
            trabajador_id INTEGER,
            creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)
    # instalaciones previas a la columna email
    ejecutar('ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS email TEXT;')
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
    if _PILOTO and username not in _PILOTO and username not in _ADMINS:
        return None, None
    if username in _cache_usuarios:
        return _cache_usuarios[username]
    resultado = (_buscar_en_nomina(username) if _MODO == 'nomina'
                 else _obtener_o_crear_local(username))
    if resultado[0]:
        _cache_usuarios[username] = resultado
    return resultado


def _buscar_en_nomina(correo: str) -> tuple:
    """Modo nomina: el correo del buzón debe existir en el directorio central.
    Devuelve el MISMO id que usa el resto del sistema (un almacén por persona)."""
    filas = consultar("""
        SELECT id, role FROM usuarios
        WHERE LOWER(email) = %s AND active = TRUE
        ORDER BY id LIMIT 1
    """, (correo,), nomina=True)
    if not filas:
        log.info('Buzón %s sin usuario en el directorio central: acceso denegado', correo)
        return None, None
    uid = filas[0]['id']
    rol = filas[0]['role'] or 'user'
    if correo in _ADMINS and rol not in ('master', 'master_admin'):
        rol = 'master'
    return uid, rol


def _obtener_o_crear_local(username: str) -> tuple:
    """Modo local: id y rol del directorio propio; lo crea si no existe.
    El rol se sincroniza con ALMACEN_ADMINS (caché por proceso)."""
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
            INSERT INTO usuarios (username, email, full_name, role)
            VALUES (%s, %s, %s, %s) ON CONFLICT (username) DO NOTHING
        """, (username, username,
              username.split('@')[0].replace('.', ' ').title(), rol_esperado))
        filas = consultar('SELECT id, role FROM usuarios WHERE username = %s', (username,))
        if not filas:
            return None, None
        uid, rol = filas[0]['id'], filas[0]['role']
    return uid, rol
