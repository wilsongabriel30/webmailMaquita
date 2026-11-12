# -*- coding: utf-8 -*-
"""Enlaces cortos del Drive Maquita: https://nube.example.org/a/X7k2Qm9P

Pedido de Wilson (06/10/2026): los enlaces del Drive eran enormes
(`/archivos-almacen/editar?ruta=%2Funidades%2F12%2F...`) y dejaban a la vista
la ruta y el nombre del archivo. El enlace corto es un código al azar que no
dice nada del archivo.

Reglas:
  · El código NO da acceso: abrirlo exige sesión de Raíces y permiso sobre el
    archivo, igual que el enlace largo (el editor valida el permiso al pedir la
    configuración). Para dar acceso a alguien de fuera sigue estando /s/<token>.
  · Un archivo tiene un solo código, para siempre. Se guarda su ubicación
    FÍSICA, así el enlace sigue funcionando si se mueve o se renombra
    (`reubicar`, llamado desde nucleo_archivos).
  · Se sirve sin redirección (regla de conexiones lentas): /a/<código> entrega
    la página del editor directamente. Las carpetas sí van al explorador.
"""
import json
import logging
import os
import secrets
from urllib.parse import quote

from flask import Blueprint, abort, jsonify, redirect, request

from almacen_bd import consultar, ejecutar
from config_almacen import URL_LINKS
from seguridad_rutas import normalizar_ruta_virtual, ruta_fisica

log = logging.getLogger('almacen.enlaces_cortos')

bp_enlaces_cortos = Blueprint('almacen_enlaces_cortos', __name__)

# Sin 0/O, 1/l/I: el código se puede dictar por teléfono sin confusiones.
_ALFABETO = 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'
_LARGO = 8
_esquema_listo = False


def _asegurar_esquema():
    global _esquema_listo
    if _esquema_listo:
        return
    ejecutar("""
        CREATE TABLE IF NOT EXISTS enlaces_cortos (
            codigo      TEXT PRIMARY KEY,
            fisica      TEXT NOT NULL UNIQUE,   -- ubicación real en disco
            ruta        TEXT NOT NULL,          -- ruta virtual canónica (ver _canonica)
            creado_por  INTEGER,
            creado_en   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            usos        INTEGER NOT NULL DEFAULT 0,
            ultimo_uso  TIMESTAMPTZ
        );
        CREATE INDEX IF NOT EXISTS ix_enlaces_cortos_fisica_prefijo
            ON enlaces_cortos (fisica text_pattern_ops);
    """)
    _esquema_listo = True


def _canonica(usuario_id, ruta):
    """La ruta que sirve a cualquiera: lo personal se expresa como
    /compartido/<dueño>/…, igual que el enlace interno del explorador."""
    if ruta.startswith('/unidades/') or ruta.startswith('/compartido/'):
        return ruta
    return '/compartido/%d%s' % (int(usuario_id), ruta)


def _para(usuario_id, canonica):
    """La ruta canónica vista por quien abre: su propio espacio, sin prefijo."""
    propio = '/compartido/%d/' % int(usuario_id)
    return canonica[len(propio) - 1:] if canonica.startswith(propio) else canonica


def codigo_de(usuario_id, ruta):
    """El código del archivo (lo crea la primera vez). Exige que quien lo pide
    pueda ver el archivo."""
    _asegurar_esquema()
    ruta = normalizar_ruta_virtual(ruta)
    fisica = os.path.realpath(ruta_fisica(usuario_id, ruta))
    if not os.path.exists(fisica):
        raise FileNotFoundError(ruta)
    fila = consultar('SELECT codigo FROM enlaces_cortos WHERE fisica = %s', (fisica,))
    if fila:
        return fila[0]['codigo']
    for _ in range(5):
        codigo = ''.join(secrets.choice(_ALFABETO) for _ in range(_LARGO))
        nueva = ejecutar(
            'INSERT INTO enlaces_cortos (codigo, fisica, ruta, creado_por) '
            'VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING RETURNING codigo',
            (codigo, fisica, _canonica(usuario_id, ruta), int(usuario_id)))
        if nueva:
            return nueva['codigo']
        fila = consultar('SELECT codigo FROM enlaces_cortos WHERE fisica = %s', (fisica,))
        if fila:                                   # otra petición lo creó a la vez
            return fila[0]['codigo']
    raise RuntimeError('No se pudo crear el enlace corto')


def url_de(codigo):
    return URL_LINKS.rstrip('/') + '/a/' + codigo


def reubicar(origen_fisico, destino_fisico, usuario_id, ruta_nueva):
    """Tras mover o renombrar: el código sigue al archivo (y a lo que haya
    dentro, si es una carpeta). Nunca lanza: mover no puede fallar por esto."""
    try:
        _asegurar_esquema()
        origen = os.path.realpath(origen_fisico).rstrip('/')
        destino = os.path.realpath(destino_fisico).rstrip('/')
        canonica = _canonica(usuario_id, normalizar_ruta_virtual(ruta_nueva)).rstrip('/')
        patron = origen.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '/%'
        filas = consultar('SELECT codigo, fisica FROM enlaces_cortos '
                          'WHERE fisica = %s OR fisica LIKE %s', (origen, patron))
        for fila in filas:
            resto = fila['fisica'][len(origen):]          # '' o '/sub/archivo'
            ejecutar('UPDATE enlaces_cortos SET fisica = %s, ruta = %s WHERE codigo = %s',
                     (destino + resto, canonica + resto, fila['codigo']))
    except Exception as excepcion:
        log.warning('enlaces cortos: no se pudo reubicar %s → %s (%s)',
                    origen_fisico, destino_fisico, excepcion)


# ── API y página ─────────────────────────────────────────────────────────
@bp_enlaces_cortos.route('/api/almacen/enlace-corto')
def api_enlace_corto():
    from api_archivos import usuario_actual
    ruta = request.args.get('ruta', '')
    try:
        codigo = codigo_de(usuario_actual(), ruta)
    except FileNotFoundError:
        return jsonify({'success': False, 'error': 'El archivo no existe'}), 404
    except Exception as excepcion:
        log.warning('enlace corto de %s: %s', ruta, excepcion)
        return jsonify({'success': False, 'error': 'No se pudo crear el enlace'}), 400
    return jsonify({'success': True, 'codigo': codigo, 'url': url_de(codigo)})


@bp_enlaces_cortos.route('/a/<codigo>')
def abrir(codigo):
    from flask_login import current_user
    if not current_user.is_authenticated:
        return redirect('/auth/iniciar-sesion?next=' + quote('/a/' + codigo))
    from integracion_faro import _acceso_almacen
    if not _acceso_almacen():
        abort(403)
    if len(codigo) != _LARGO or any(c not in _ALFABETO for c in codigo):
        abort(404)
    _asegurar_esquema()
    fila = consultar('UPDATE enlaces_cortos SET usos = usos + 1, ultimo_uso = NOW() '
                     'WHERE codigo = %s RETURNING fisica, ruta', (codigo,))
    if not fila:
        abort(404)
    from api_archivos import usuario_actual
    ruta = _para(usuario_actual(), fila[0]['ruta'])
    # Sin permiso no se entrega ni la página: llevaría dentro la ruta y el
    # nombre del archivo, que es justo lo que el enlace corto esconde.
    try:
        if not os.path.exists(ruta_fisica(usuario_actual(), ruta)):
            abort(404)
    except Exception as excepcion:
        if getattr(excepcion, 'code', None) == 404:
            raise
        return _sin_acceso()
    if os.path.isdir(fila[0]['fisica']):
        return redirect('/archivos-almacen' + quote(ruta))
    from api_onlyoffice import abrir_editor
    return abrir_editor(ruta, enlace={'ruta': ruta, 'codigo': codigo})


def _sin_acceso():
    html = ('<!doctype html><html lang="es"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Sin acceso — Drive Maquita</title></head>'
            '<body style="font:16px system-ui,sans-serif;max-width:32rem;margin:15vh auto;padding:0 16px;color:#202124">'
            '<h1 style="font-size:1.4rem">No tienes acceso a este archivo</h1>'
            '<p>Pide a quien te envió el enlace que lo comparta contigo desde el Drive Maquita.</p>'
            '<p><a href="/archivos-almacen">Ir a mi Drive</a></p></body></html>')
    return html, 403, {'Content-Type': 'text/html; charset=utf-8'}


def script_enlace(enlace):
    """<script> que le pasa a la página del editor la ruta del enlace corto."""
    datos = json.dumps(enlace, ensure_ascii=False).replace('</', '<\\/')
    return '<script>window.__ENLACE_CORTO__ = %s;</script>' % datos
