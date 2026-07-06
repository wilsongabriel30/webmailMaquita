# -*- coding: utf-8 -*-
"""
Sincroniza los usuarios desde la fuente de identidad (el correo/directorio) hacia
la tabla local `usuarios` del servicio de chat.

Por qué existe
--------------
El chat es un servicio INDEPENDIENTE con su propia base de datos. Sus tablas
(conversaciones, mensajes, participantes…) referencian `usuarios.id` por clave
foránea, así que el chat necesita una copia local mínima de cada usuario
(id, correo, nombre, avatar). NO guarda contraseñas: la autenticación llega por
JWT emitido por el correo (o, más adelante, por Keycloak).

Para quien adopta este proyecto
--------------------------------
La "fuente" es tu propio directorio de correo/usuarios. Ajusta USERS_DB_URL y, si
tu esquema difiere, la consulta SELECT de abajo. El identificador que viaja en el
JWT es el CORREO; aquí se resuelve a un id local estable. Ejecuta este script de
forma periódica (cron) o dispáralo desde tu alta de usuarios.

Uso:
  DATABASE_URL=... USERS_DB_URL=... venv/bin/python3 sincronizar_usuarios.py
"""
import os
import sys

import psycopg2
from psycopg2.extras import execute_values


def _conn(url):
    return psycopg2.connect(url)


def sincronizar():
    origen_url = os.environ["USERS_DB_URL"]
    destino_url = os.environ["DATABASE_URL"]

    # Fuente de identidad. Ajustar el SELECT al esquema propio si difiere.
    consulta_origen = """
        SELECT id, username, email, COALESCE(full_name, username) AS full_name,
               COALESCE(active, true) AS active, profile_picture
        FROM usuarios
        WHERE email IS NOT NULL
    """

    with _conn(origen_url) as co, co.cursor() as cur_o:
        cur_o.execute(consulta_origen)
        filas = cur_o.fetchall()

    if not filas:
        print("No hay usuarios en la fuente. Nada que sincronizar.")
        return 0

    # password_hash es NOT NULL en el modelo del chat, pero el chat NO autentica con
    # contraseña (usa el JWT del correo). Se guarda un marcador no utilizable.
    registros = [
        (uid, uname, email, "external-idp", full_name, bool(active), avatar)
        for (uid, uname, email, full_name, active, avatar) in filas
    ]

    upsert = """
        INSERT INTO usuarios
            (id, username, email, password_hash, full_name, active, profile_picture)
        VALUES %s
        ON CONFLICT (id) DO UPDATE SET
            username = EXCLUDED.username,
            email = EXCLUDED.email,
            full_name = EXCLUDED.full_name,
            active = EXCLUDED.active,
            profile_picture = EXCLUDED.profile_picture
    """

    with _conn(destino_url) as cd, cd.cursor() as cur_d:
        execute_values(cur_d, upsert, registros)
        # Mantener el contador de la secuencia por delante del máximo id insertado.
        cur_d.execute("SELECT setval(pg_get_serial_sequence('usuarios','id'), "
                      "(SELECT COALESCE(MAX(id), 1) FROM usuarios))")
        cd.commit()

    print(f"OK — {len(registros)} usuarios sincronizados en la BD del chat.")
    return len(registros)


if __name__ == "__main__":
    try:
        sincronizar()
    except KeyError as e:
        print(f"Falta variable de entorno: {e}", file=sys.stderr)
        sys.exit(1)
