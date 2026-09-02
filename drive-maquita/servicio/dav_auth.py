# -*- coding: utf-8 -*-
"""
Autenticación por TOKEN DAV (la que usa la app de Windows).
===========================================================
QUÉ: resuelve qué usuario de FARO hay detrás de un HTTP Basic cuyo usuario es
el ID de FARO y cuya contraseña es el token del equipo — el mismo token con el
que se monta el disco por WebDAV.

POR QUÉ AQUÍ: lo necesitan varios endpoints de la app (compartir, revocar el
equipo, enviar registros de error). Vive en su propio módulo para que la regla
de autenticación sea UNA sola y no una copia por endpoint.

Estos endpoints no usan sesión ni CSRF: su credencial es el token. Por eso van
exentos del «candado» de sesión de /api/almacen (ver integracion_faro.py).

Autoría: Equipo de Tecnología Maquita — 2026-08-04
"""
import hashlib

from almacen_bd import consultar


def hash_token(token):
    """Huella del token tal como se guarda en `dav_tokens.token_hash`."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def usuario_por_token(auth):
    """ID de usuario dueño del token Basic, o None si no vale.

    Comprueba además que el usuario del Basic coincida con el dueño del token:
    no basta con saber un token para hacerse pasar por otro id.
    """
    if not auth or not auth.username or not auth.password:
        return None
    filas = consultar(
        "SELECT usuario_id FROM dav_tokens "
        " WHERE token_hash = %s AND revocado IS NULL", (hash_token(auth.password),))
    if not filas:
        return None
    dueno = filas[0]['usuario_id']
    try:
        if int(auth.username) != int(dueno):
            return None
    except (TypeError, ValueError):
        return None
    return dueno


def token_id_por_token(auth):
    """(usuario_id, token_id) del token Basic, o (None, None).

    El id del token hace falta para revocar EXACTAMENTE el equipo que llama,
    sin tocar los demás equipos de la misma persona.
    """
    if not auth or not auth.username or not auth.password:
        return None, None
    filas = consultar(
        "SELECT id, usuario_id FROM dav_tokens "
        " WHERE token_hash = %s AND revocado IS NULL", (hash_token(auth.password),))
    if not filas:
        return None, None
    dueno = filas[0]['usuario_id']
    try:
        if int(auth.username) != int(dueno):
            return None, None
    except (TypeError, ValueError):
        return None, None
    return dueno, filas[0]['id']
