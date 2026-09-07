# -*- coding: utf-8 -*-
"""[Q-2] Quita de reuniones_programadas los JWT de Meet que se guardaban (token_moderador,
token_invitado y el ?jwt= de enlace_moderador). Idempotente. Uso: venv/bin/python purgar_tokens_reuniones.py"""
import os
import re

import psycopg2

dsn = os.getenv("DATABASE_URL")
if not dsn:
    raise SystemExit("Falta DATABASE_URL")
with psycopg2.connect(dsn) as con, con.cursor() as cur:
    cur.execute("""UPDATE reuniones_programadas
                      SET token_moderador = NULL, token_invitado = NULL,
                          enlace_moderador = regexp_replace(enlace_moderador, '\\?jwt=.*$', '')
                    WHERE token_moderador IS NOT NULL OR token_invitado IS NOT NULL
                       OR enlace_moderador LIKE '%?jwt=%'""")
    print("filas purgadas:", cur.rowcount)
