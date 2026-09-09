# -*- coding: utf-8 -*-
"""Columnas que el código necesita y la base todavía no tiene (aviso de Andes, 08/09/2026).

`create_all` crea las TABLAS que faltan, nunca las COLUMNAS de una tabla que ya existe. Así, una
columna añadida al modelo más tarde no llegaba a ninguna instalación: ni a las nuevas, si el
modelo tampoco la declaraba, ni a las viejas. Le pasó a `chat_participants.cleared_at`: el código
la leía, la consulta fallaba, el error se tragaba con un `except` y dejaba la transacción
envenenada, de modo que la siguiente consulta —correcta— respondía 500.

Aquí se calcula qué falta comparando el modelo con la base. Solo se AÑADE: nunca se borra ni se
cambia el tipo de nada, porque eso no puede hacerse a ciegas.
"""


def columnas_a_anadir(modelo, existentes):
    """Nombres de columnas del modelo que no están en la base.

    `modelo`: [(nombre, tipo_sql, admite_nulos)]. `existentes`: nombres que ya hay.
    """
    hay = {c.strip().lower() for c in existentes}
    return [(n, t, nulo) for (n, t, nulo) in modelo if n.strip().lower() not in hay]


def sentencia(tabla, nombre, tipo_sql, admite_nulos=True):
    """`ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, sin sorpresas.

    Una columna nueva sobre una tabla con datos SOLO puede admitir nulos: exigir valor obligaría
    a inventarse uno para las filas que ya están.
    """
    if not admite_nulos:
        raise ValueError(
            "una columna nueva sobre datos existentes tiene que admitir nulos: %s.%s" % (tabla, nombre))
    return 'ALTER TABLE %s ADD COLUMN IF NOT EXISTS %s %s' % (tabla, nombre, tipo_sql)


def plan(tabla, modelo, existentes):
    """Las sentencias necesarias, en orden. Lista vacía si no falta nada."""
    return [sentencia(tabla, n, t, nulo) for (n, t, nulo) in columnas_a_anadir(modelo, existentes)]
