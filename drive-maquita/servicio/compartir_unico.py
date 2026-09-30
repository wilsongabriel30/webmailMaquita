# -*- coding: utf-8 -*-
"""Una persona, un acceso: compartir dos veces no crea dos permisos.

Responsabilidad ÚNICA: decir si esa persona YA tiene un acceso del mismo dueño
sobre esa misma ruta, para que compartir de nuevo lo ACTUALICE en vez de añadir
otro.

EL PROBLEMA (29/09/2026)
Cada vez que se compartía algo con la misma persona se guardaba una fila nueva.
Con dos filas —una de lector y otra de editor— mandaba la más generosa: la
dueña bajaba a «Lector» a alguien en «Personas con acceso» y esa persona seguía
pudiendo subir y borrar, porque quedaba la otra fila.

Los enlaces públicos no entran aquí: no van dirigidos a nadie y una carpeta
puede tener más de uno (con clave, con caducidad…).
"""

from almacen_bd import consultar

TIPO_ENLACE = 3


def acceso_previo(propietario_id, ruta, tipo, destinatario, email):
    """Fila {id, token} del acceso que esa persona ya tiene, o None."""
    if int(tipo) == TIPO_ENLACE:
        return None
    destinatario = (destinatario or '').strip()
    email = (email or '').strip().lower()
    if not destinatario and not email:
        return None
    filas = consultar("""
        SELECT id, token FROM compartidos
        WHERE propietario_id = %s AND ruta = %s AND tipo <> %s
          AND ((%s <> '' AND destinatario = %s) OR (%s <> '' AND LOWER(email) = %s))
        ORDER BY id LIMIT 1
    """, (int(propietario_id), ruta, TIPO_ENLACE,
          destinatario, destinatario, email, email))
    return dict(filas[0]) if filas else None
