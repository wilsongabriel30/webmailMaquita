# -*- coding: utf-8 -*-
"""A quién pertenece cada id del directorio del chat (aviso serio de Andes, 08/09/2026).

La identidad de una persona es su CORREO. Numerar por posición (`row_number() ORDER BY ...`)
parecía estable y no lo era: dar de alta un buzón que ordena primero desplazaba a todos, y con
un `ON CONFLICT (id)` las conversaciones y los mensajes de alguien quedaban atribuidos a otra
persona. Aquí se decide el id de cada fila sin que un alta o una baja mueva a nadie.
"""


def asignar_ids(filas, conocidos, siguiente_libre):
    """Devuelve (filas con id, cuántas son nuevas).

    - `filas`: tuplas (id_de_origen_o_None, usuario, correo, marca, nombre, activo, avatar).
    - `conocidos`: {correo en minúsculas: id que ya tiene en el directorio}.
    - `siguiente_libre`: primer id libre (normalmente MAX(id) + 1).

    Quien ya está conserva su id. Quien trae id propio de una fuente con ids (un directorio
    replicado) lo mantiene. Quien es nuevo recibe el siguiente libre.
    """
    salida = []
    nuevos = 0
    siguiente = int(siguiente_libre)
    for fila in filas:
        id_origen, usuario, correo, marca, nombre, activo, avatar = fila
        clave = (correo or "").strip().lower()
        if clave in conocidos:
            asignado = conocidos[clave]
        elif id_origen is not None:
            asignado = id_origen
        else:
            asignado = siguiente
            siguiente += 1
            nuevos += 1
        salida.append((asignado, usuario, correo, marca, nombre, bool(activo), avatar))
    return salida, nuevos
