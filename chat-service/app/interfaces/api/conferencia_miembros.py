# -*- coding: utf-8 -*-
"""
Quién estuvo en cada conferencia.
=================================
[A-5] Las grabaciones de conferencia se protegían con `_usuario_en_sala`, que
daba por bueno a CUALQUIER usuario autenticado si la sala empezaba por `conf_`.
Bastaba con conocer o adivinar el identificador de la sala para iniciar, detener
y descargar la grabación de una reunión ajena.

No se podía comprobar contra nada porque las salas se nombran en el navegador
(`conf_<marca de tiempo>_<azar>`) y no se atan a ninguna conversación. La lista
de participantes existía solo en memoria del proceso y se perdía en cada
reinicio, mientras que las grabaciones sobreviven.

Aquí se persiste esa pertenencia: quien crea una conferencia y quien se une
quedan registrados, y a partir de eso se decide quién puede tocar su grabación.
Cada persona entra con su cuenta institucional, así que el registro identifica
a alguien real y sirve además como rastro de quién asistió.
"""
import logging
import os

import psycopg2

log = logging.getLogger('chat.conferencia_miembros')

_tabla_lista = False


def _conexion():
    return psycopg2.connect(os.getenv('DATABASE_URL'))


def asegurar_tabla():
    """Crea la tabla si no existe. Idempotente."""
    global _tabla_lista
    if _tabla_lista:
        return
    try:
        with _conexion() as con, con.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_conferencia_miembros (
                    room       TEXT        NOT NULL,
                    usuario_id INTEGER     NOT NULL,
                    unido_en   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (room, usuario_id)
                )
            """)
            con.commit()
        _tabla_lista = True
    except Exception as excepcion:
        log.warning('No se pudo preparar chat_conferencia_miembros: %s', excepcion)


def registrar(room, usuario_id) -> None:
    """Deja constancia de que este usuario estuvo en esa conferencia."""
    if not room or not usuario_id:
        return
    asegurar_tabla()
    try:
        with _conexion() as con, con.cursor() as cur:
            cur.execute(
                'INSERT INTO chat_conferencia_miembros (room, usuario_id) '
                'VALUES (%s, %s) ON CONFLICT (room, usuario_id) DO NOTHING',
                (str(room)[:100], int(usuario_id)))
            con.commit()
    except Exception as excepcion:
        log.warning('No se pudo registrar la pertenencia a %s: %s', room, excepcion)


def estuvo_en(room, usuario_id) -> bool:
    """True solo si consta que el usuario estuvo en esa conferencia.

    Falla CERRADO: si la consulta no se puede hacer, no se concede acceso.
    """
    if not room or not usuario_id:
        return False
    try:
        with _conexion() as con, con.cursor() as cur:
            cur.execute(
                'SELECT 1 FROM chat_conferencia_miembros '
                'WHERE room = %s AND usuario_id = %s LIMIT 1',
                (str(room)[:100], int(usuario_id)))
            return cur.fetchone() is not None
    except Exception as excepcion:
        log.warning('No se pudo comprobar la pertenencia a %s: %s', room, excepcion)
        return False
