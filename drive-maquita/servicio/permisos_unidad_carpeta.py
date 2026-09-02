"""Permisos por CARPETA dentro de una unidad compartida.

Responsabilidad ÚNICA: calcular el rol efectivo de un usuario sobre una ruta
concreta de una unidad, y gestionar las concesiones por carpeta.

MODELO AMPLIATIVO, como las Unidades compartidas de Google (decisión de Wilson,
2026-07-28): el permiso de carpeta **solo puede subir** el nivel que ya se tiene
en la unidad, nunca bajarlo. Dos consecuencias:

  1. Un `viewer` de la unidad puede ser `editor` en `/Contabilidad`.
  2. Alguien que NO es miembro de la unidad puede tener acceso a UNA carpeta.
     Es la «folder-level access» que Google añadió a las Unidades compartidas.

Para QUITAR acceso no se usa un rol menor: se quita la concesión, o se saca al
usuario de la unidad. Bajar por carpeta exigiría un modelo restrictivo, que es
justo lo que se descartó.

El rol efectivo se hereda hacia abajo: una concesión sobre `/Contabilidad`
alcanza a `/Contabilidad/2026/enero.xlsx`. Si hay varias que cubren la ruta,
gana **la de mayor rango**, no la más específica — coherente con «amplía».
"""

import logging

from almacen_bd import consultar, ejecutar

log = logging.getLogger('almacen.permisos_unidad_carpeta')

ROLES = ('viewer', 'editor', 'manager')
_RANGO = {'viewer': 1, 'editor': 2, 'manager': 3}


def rango(rol):
    return _RANGO.get(rol or '', 0)


def rol_en_carpeta(usuario_id, unidad_id, sub_ruta):
    """Mayor rol concedido por carpeta que cubre `sub_ruta`, o None.

    La consulta compara por prefijo con el parámetro del cliente SIEMPRE en el
    lado izquierdo del LIKE: al revés, un '%' en la ruta actuaría de comodín.
    """
    sub = '/' + (sub_ruta or '').strip('/')
    filas = consultar(
        "SELECT rol FROM unidad_permisos_carpeta "
        "WHERE unidad_id = %s AND usuario_id = %s "
        "AND (ruta = %s OR %s LIKE ruta || '/%%')",
        (int(unidad_id), int(usuario_id), sub, sub))
    mejor = None
    for fila in filas:
        if rango(fila['rol']) > rango(mejor):
            mejor = fila['rol']
    return mejor


def rol_efectivo(usuario_id, unidad_id, sub_ruta):
    """Rol real sobre esa ruta: el MAYOR entre el de la unidad y el de carpeta.

    Devuelve None si no tiene ninguno de los dos, es decir, sin acceso.
    """
    # Desde `roles_unidad`, NO desde api_unidades: este cálculo también lo hace
    # el servicio WebDAV, que no tiene Flask (01/09/2026).
    from roles_unidad import rol_en_unidad
    de_unidad = rol_en_unidad(usuario_id, unidad_id)
    de_carpeta = rol_en_carpeta(usuario_id, unidad_id, sub_ruta)
    if rango(de_carpeta) > rango(de_unidad):
        return de_carpeta
    return de_unidad


def conceder(unidad_id, ruta, usuario_id, rol, creado_por=None):
    """Concede (o cambia) el rol de un usuario sobre una carpeta de la unidad."""
    if rol not in ROLES:
        raise ValueError('Rol inválido: %s' % rol)
    ruta = '/' + (ruta or '').strip('/')
    ejecutar(
        "INSERT INTO unidad_permisos_carpeta (unidad_id, ruta, usuario_id, rol, creado_por) "
        "VALUES (%s, %s, %s, %s, %s) "
        "ON CONFLICT (unidad_id, ruta, usuario_id) DO UPDATE SET "
        "rol = EXCLUDED.rol, creado_por = EXCLUDED.creado_por, creado_en = NOW()",
        (int(unidad_id), ruta, int(usuario_id), rol,
         int(creado_por) if creado_por else None))
    return {'unidad_id': int(unidad_id), 'ruta': ruta,
            'usuario_id': int(usuario_id), 'rol': rol}


def revocar(unidad_id, ruta, usuario_id):
    """Quita la concesión. El usuario vuelve a su rol de unidad (o a ninguno)."""
    ruta = '/' + (ruta or '').strip('/')
    ejecutar(
        "DELETE FROM unidad_permisos_carpeta "
        "WHERE unidad_id = %s AND ruta = %s AND usuario_id = %s",
        (int(unidad_id), ruta, int(usuario_id)))
    return True


def listar(unidad_id, ruta=None):
    """Concesiones de la unidad, o solo las de una carpeta concreta."""
    if ruta is None:
        return [dict(f) for f in consultar(
            "SELECT * FROM unidad_permisos_carpeta WHERE unidad_id = %s "
            "ORDER BY ruta, usuario_id", (int(unidad_id),))]
    ruta = '/' + (ruta or '').strip('/')
    return [dict(f) for f in consultar(
        "SELECT * FROM unidad_permisos_carpeta WHERE unidad_id = %s AND ruta = %s "
        "ORDER BY usuario_id", (int(unidad_id), ruta))]
