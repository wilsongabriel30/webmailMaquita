# -*- coding: utf-8 -*-
"""Rutas internas que se enviaron por error como si fueran el enlace público.

Responsabilidad ÚNICA: para las carpetas de una lista EXPLÍCITA, llevar a su
enlace público a quien abre la dirección interna y no tiene otro camino.

EL PROBLEMA (29/09/2026)
Se mandó por correo `/archivos-almacen/FV. 1er semestre` —la dirección de la
barra del navegador de la dueña— en lugar del enlace de «Copiar enlace». Esa
dirección apunta al espacio de QUIEN ENTRA: a los demás les pide iniciar sesión
y luego no encuentra la carpeta. El correo ya salió y no se puede corregir.

QUÉ SE HACE
  · Quien tiene la carpeta en su espacio (la dueña) → sigue como siempre.
  · A quien se la compartieron por su cuenta → sigue como siempre: entra por
    «Compartido conmigo» con el permiso que le dieron (lector o editor).
  · Cualquier otra persona, con o sin sesión → al enlace público de la carpeta,
    con el permiso que ese enlace tenga.

LO QUE NO SE HACE
No vale para cualquier carpeta que tenga enlace público (ver resolver_enlace.py:
el enlace lo reparte su dueño). Solo para las que Tecnología anota en
`config_kv`, clave `rutas_internas_publicas`, como lista JSON:
    [{"propietario_id": 46, "ruta": "/FV. 1er semestre"}]
Un enlace con clave o caducado no se usa: la dirección vuelve a su
comportamiento normal.
"""

import json
import logging
import time

log = logging.getLogger('almacen.ruta_publicada')

CLAVE_CONFIG = 'rutas_internas_publicas'
_PREFIJO_WEB = '/archivos-almacen/'
_SEGUNDOS_CACHE = 60

_cache = {'hasta': 0.0, 'lista': []}


def _publicadas():
    """Lista de (propietario_id, ruta) anotadas. Se relee cada minuto."""
    ahora = time.time()
    if ahora < _cache['hasta']:
        return _cache['lista']
    lista = []
    try:
        from almacen_bd import consultar
        from seguridad_rutas import normalizar_ruta_virtual
        filas = consultar('SELECT valor FROM config_kv WHERE clave = %s',
                          (CLAVE_CONFIG,))
        if filas and filas[0]['valor']:
            for entrada in json.loads(filas[0]['valor']):
                ruta = normalizar_ruta_virtual(entrada['ruta'])
                if ruta != '/':
                    lista.append((int(entrada['propietario_id']), ruta))
    except Exception as excepcion:
        log.warning('No se pudo leer %s: %s', CLAVE_CONFIG, excepcion)
        lista = []
    _cache['lista'] = lista
    _cache['hasta'] = ahora + _SEGUNDOS_CACHE
    return lista


def _anotada(ruta):
    """(propietario_id, ruta_publicada, resto) si la ruta es una anotada o
    cuelga de ella. None si no."""
    for propietario_id, publicada in _publicadas():
        if ruta == publicada:
            return propietario_id, publicada, ''
        if ruta.startswith(publicada + '/'):
            return propietario_id, publicada, ruta[len(publicada):]
    return None


def _token_publico(propietario_id, ruta):
    """Token del enlace público vigente y sin clave de esa carpeta."""
    from almacen_bd import consultar
    filas = consultar("""
        SELECT token FROM compartidos
        WHERE propietario_id = %s AND ruta = %s AND tipo = 3
          AND token IS NOT NULL AND clave_hash IS NULL
          AND (expira_en IS NULL OR expira_en > now())
        ORDER BY id DESC LIMIT 1
    """, (propietario_id, ruta))
    return filas[0]['token'] if filas else None


def destino_publico(usuario_id, ruta):
    """Dirección del enlace público a la que llevar a esta persona, o None.

    `usuario_id` es None cuando quien entra no tiene sesión.
    """
    from seguridad_rutas import RutaInvalida, normalizar_ruta_virtual
    try:
        limpia = normalizar_ruta_virtual(ruta)
    except RutaInvalida:
        return None
    anotada = _anotada(limpia)
    if not anotada:
        return None
    propietario_id, publicada, resto = anotada

    if usuario_id:
        from resolver_enlace import _quien_me_lo_comparte, existe_para
        if existe_para(usuario_id, limpia):
            return None                  # la tiene en su espacio
        if _quien_me_lo_comparte(usuario_id, limpia):
            return None                  # se la compartieron: entra con su permiso

    token = _token_publico(propietario_id, publicada)
    if not token:
        return None
    from urllib.parse import quote
    return '/s/' + token + quote(resto)


def registrar(app):
    """Engancha la comprobación ANTES del candado de sesión del Almacén: quien
    llega sin sesión tiene que poder abrir la carpeta sin pasar por el login."""
    from flask import redirect, request, session
    from flask_login import current_user

    @app.before_request
    def _ruta_interna_publicada():
        try:
            if request.method != 'GET':
                return None
            camino = request.path or ''
            if not camino.startswith(_PREFIJO_WEB):
                return None
            if not _publicadas():
                return None
            usuario_id = session.get('usuario_id')
            if not usuario_id and getattr(current_user, 'is_authenticated', False):
                usuario_id = current_user.id
            destino = destino_publico(int(usuario_id) if usuario_id else None,
                                      '/' + camino[len(_PREFIJO_WEB):])
            if destino:
                log.info('Ruta interna publicada %s -> enlace público (usuario %s)',
                         camino, usuario_id or 'sin sesión')
                return redirect(destino, 302)
        except Exception as excepcion:
            # Ante cualquier fallo, la dirección se comporta como siempre.
            log.warning('Ruta publicada no resuelta: %s', excepcion)
        return None

    log.info('Rutas internas publicadas: comprobación activa')
