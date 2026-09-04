# -*- coding: utf-8 -*-
"""El rol de una persona en una unidad compartida.

Responsabilidad ÚNICA, y sin dependencias web a propósito: esta regla la
necesitan la web (FARO) y el **disco montado** (servicio WebDAV, que corre
aparte y no tiene Flask). Vivía dentro de `api_unidades`, que importa Flask, y
por eso al calcularla desde el WebDAV saltaba `ModuleNotFoundError: flask`:
el cálculo por carpeta fallaba en silencio y degradaba a «lector» a quien era
editor de una carpeta (01/09/2026).

Aquí no se importa nada de Flask. `api_unidades` la reexporta para que el resto
del código la siga llamando igual.
"""

from almacen_bd import consultar, es_master


def rol_en_unidad(usuario_id, unidad_id):
    """Rol del usuario en la unidad, o None si no es miembro.
    El master del Drive lo ve todo como manager."""
    filas = consultar(
        'SELECT rol FROM unidad_miembros WHERE unidad_id = %s AND usuario_id = %s',
        (unidad_id, usuario_id))
    if filas:
        return filas[0]['rol']
    return 'manager' if es_master(usuario_id) else None


class SinPermisoUnidad(Exception):
    """El usuario no es miembro de la unidad (ni tiene concesión por carpeta),
    o su rol no permite escribir. `seguridad_rutas` la convierte en RutaInvalida."""


def exigir_permiso_unidad(usuario_id, unidad_id, sub_ruta='/', escritura=False) -> str:
    """Devuelve el rol efectivo si el usuario puede leer (o escribir) `sub_ruta`
    dentro de la unidad. Lanza SinPermisoUnidad si no; también si la BD falla
    (cerrado). Usa el rol ampliado por carpeta y cae al rol de unidad si ese
    cálculo falla, igual que `api_unidades.permiso_unidad` (C-7, 2026-09)."""
    import logging
    log = logging.getLogger('almacen.roles_unidad')
    try:
        try:
            from permisos_unidad_carpeta import rol_efectivo
            rol = rol_efectivo(usuario_id, unidad_id, sub_ruta)
        except Exception as excepcion:
            log.warning('rol_efectivo falló (se usa el rol de unidad): %s', excepcion)
            rol = rol_en_unidad(usuario_id, unidad_id)
    except Exception as excepcion:
        log.error('No se pudo comprobar el permiso de la unidad %s para el usuario %s: %s',
                  unidad_id, usuario_id, excepcion)
        raise SinPermisoUnidad('No se pudo comprobar el permiso de la unidad compartida') from excepcion
    if rol is None:
        log.warning('Acceso denegado: usuario %s sin acceso a la unidad %s (%s)', usuario_id, unidad_id, sub_ruta)
        raise SinPermisoUnidad('No eres miembro de esta unidad compartida')
    if escritura and rol == 'viewer':
        raise SinPermisoUnidad('Solo tienes permiso de lectura en esta unidad compartida')
    return rol
