# -*- coding: utf-8 -*-
"""
Permisos de UNIDADES COMPARTIDAS del Almacén Maquita.
=====================================================
Regla ÚNICA de quién puede leer o escribir en `/unidades/<id>/…`. No importa
Flask: la usan `seguridad_rutas.ruta_fisica` (todo acceso a disco) y la API.

Falla CERRADO: si la base de datos no responde, no hay acceso. Antes la
comprobación era opcional (solo en algunos endpoints) y abría ante cualquier
error; cualquier sesión podía descargar, copiar o publicar por enlace el
contenido de una unidad de la que no era miembro.

Roles: manager (todo), editor (sube/edita/borra), viewer (solo lee).
Los usuarios master actúan como manager en todas las unidades.

Autoría: Equipo de Tecnología Maquita — 2026-09-03
"""
import logging

from seguridad_rutas import RutaInvalida, unidad_de_ruta

log = logging.getLogger('almacen.permisos_unidad')


class SinPermisoUnidad(RutaInvalida):
    """El usuario no es miembro de la unidad, o su rol no permite escribir."""


def rol_en_unidad(usuario_id, unidad_id):
    """Rol del usuario en la unidad, o None si no es miembro. master ve todo como manager."""
    from almacen_bd import consultar, es_master   # import interno: este módulo no depende de la BD al cargar
    filas = consultar("SELECT rol FROM unidad_miembros WHERE unidad_id = %s AND usuario_id = %s",
                      (int(unidad_id), int(usuario_id)))
    if filas:
        return filas[0]['rol']
    return 'manager' if es_master(usuario_id) else None


def exigir_permiso_unidad(usuario_id, unidad_id, escritura=False) -> str:
    """Devuelve el rol si el usuario puede leer (o escribir) en la unidad.
    Lanza SinPermisoUnidad en caso contrario, también si la BD falla (cerrado)."""
    try:
        rol = rol_en_unidad(usuario_id, unidad_id)
    except Exception as excepcion:
        log.error('No se pudo comprobar el permiso de la unidad %s para el usuario %s: %s',
                  unidad_id, usuario_id, excepcion)
        raise SinPermisoUnidad('No se pudo comprobar el permiso de la unidad compartida') from excepcion
    if rol is None:
        log.warning('Acceso denegado: usuario %s no es miembro de la unidad %s', usuario_id, unidad_id)
        raise SinPermisoUnidad('No eres miembro de esta unidad compartida')
    if escritura and rol == 'viewer':
        raise SinPermisoUnidad('Solo tienes permiso de lectura en esta unidad compartida')
    return rol


def permiso_unidad(usuario_id, ruta, escritura=False) -> bool:
    """¿Puede el usuario leer (o escribir) esta ruta si es de una unidad compartida?
    Rutas personales: True (aplica la contención personal). Falla cerrado."""
    unidad_id, _sub = unidad_de_ruta(ruta)
    if unidad_id is None:
        return True
    try:
        exigir_permiso_unidad(usuario_id, unidad_id, escritura)
    except SinPermisoUnidad:
        return False
    return True
