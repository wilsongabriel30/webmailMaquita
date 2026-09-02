# -*- coding: utf-8 -*-
"""Un enlace del Drive que no abre donde debería: ¿dónde está de verdad?

Responsabilidad ÚNICA: dada una ruta que alguien pide y que NO existe en su
espacio, decir qué hacer con ella.

EL PROBLEMA (01/09/2026)
Un enlace interno como `/archivos-almacen/Trazabilidad proyecto GO12` apunta a
esa ruta **en el espacio de quien entra**. Si la carpeta es de otra persona, a
quien la abre no le existe: el explorador lo devolvía a «Mi unidad» diciendo
que el enlace ya no existe. Y no es verdad —la carpeta está ahí, es de otro—,
así que el mensaje mandaba a buscar por el sitio equivocado.

QUÉ SE HACE AHORA
  · Si a esa persona se lo compartieron → se la lleva a la carpeta, en el
    espacio «Compartido conmigo». El permiso ya lo tenía; solo faltaba saber
    por dónde entrar.
  · Si no → se le dice **de quién es** y que se lo pida, en vez de decirle que
    no existe.

Lo que NO se hace: si la carpeta tiene un enlace público, NO se redirige ahí
sola. Ese enlace lo reparte su dueño a quien quiere; abrirlo por su cuenta a
quien llegó por otro camino sería dar un acceso que nadie concedió.
"""

import logging
import os

from seguridad_rutas import (RutaInvalida, normalizar_ruta_virtual, ruta_fisica,
                             unidad_de_ruta)

log = logging.getLogger('almacen.resolver_enlace')


def existe_para(usuario_id: int, ruta: str) -> bool:
    """¿Existe esa ruta en el espacio de esta persona?"""
    try:
        return os.path.exists(ruta_fisica(usuario_id, ruta))
    except (RutaInvalida, OSError):
        return False


def _quien_me_lo_comparte(usuario_id: int, ruta: str):
    """Dueño que le ha compartido a esta persona algo que cubre esa ruta."""
    try:
        from permisos_compartidos import concesiones, _cubre
    except Exception as excepcion:
        log.warning('No se pudieron leer las concesiones: %s', excepcion)
        return None
    limpia = normalizar_ruta_virtual(ruta)
    for concesion in concesiones(usuario_id) or []:
        try:
            if concesion.get('clave_hash'):
                # Enlace con clave: el acceso se gana en la vista del enlace.
                continue
            if _cubre(concesion['ruta'], limpia):
                return int(concesion['propietario_id'])
        except Exception:
            continue
    return None


def _de_quien_es(ruta: str):
    """(id, nombre) del dueño de esa ruta, buscándola en el índice. None si no
    se sabe: entonces es que de verdad no está."""
    try:
        from almacen_bd import consultar
        filas = consultar(
            'SELECT usuario_id FROM indice_nombres WHERE ruta = %s LIMIT 1',
            (normalizar_ruta_virtual(ruta),))
        if not filas:
            return None
        dueno = int(filas[0]['usuario_id'])
    except Exception as excepcion:
        log.warning('No se pudo buscar el dueno de %s: %s', ruta, excepcion)
        return None
    nombre = ''
    try:
        from vista_compartidos import _nombres_de
        ficha = _nombres_de({dueno}).get(dueno) or {}
        nombre = ficha.get('nombre') or ficha.get('email') or ''
    except Exception:
        pass
    return dueno, nombre


def resolver(usuario_id: int, ruta: str):
    """Qué hacer con una ruta que se pide.

    Devuelve None si no hay nada que hacer (existe, o es de una unidad, o no se
    sabe de quién es). Si hay algo:
        {'ir_a': '/compartido/104/...'}     → llevarlo allí
        {'pedir_acceso': {...}}             → enseñarle de quién es, con un
                                              botón para pedírselo
    """
    try:
        limpia = normalizar_ruta_virtual(ruta)
    except RutaInvalida:
        return None
    if limpia == '/':
        return None

    unidad, _ = unidad_de_ruta(limpia)
    if unidad is not None:
        return None                      # las unidades tienen su propio camino
    if limpia.startswith('/compartido/'):
        return None                      # ya viene por el camino bueno
    if existe_para(usuario_id, limpia):
        return None                      # todo normal

    dueno = _quien_me_lo_comparte(usuario_id, limpia)
    if dueno:
        return {'ir_a': '/compartido/%d%s' % (dueno, limpia)}

    ficha = _de_quien_es(limpia)
    if not ficha:
        return None                      # de verdad no existe
    dueno_id, nombre = ficha
    return {'pedir_acceso': {
        'propietario_id': dueno_id,
        'propietario': nombre or 'otra persona',
        'ruta': limpia,
        'nombre': os.path.basename(limpia) or limpia,
    }}
