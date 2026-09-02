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
