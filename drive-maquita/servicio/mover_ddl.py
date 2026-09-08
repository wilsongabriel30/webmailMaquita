#!/usr/bin/env python3
"""La tabla enlaces_correo debe crearse en TODOS los modos de directorio: en modo «nómina» no se llama a
asegurar_tablas_webmail() (solo directorio local), así que va al DDL general de almacen_bd.py."""
p = "almacen/servicio/auth_webmail.py"
s = open(p, encoding="utf-8").read()
bloque = """    # Vínculo explícito buzón -> persona del directorio central (lo fija el panel de administración):
    # manda sobre la coincidencia por correo. Para personas cuyo correo del directorio no es el buzón.
    ejecutar(\"\"\"
        CREATE TABLE IF NOT EXISTS enlaces_correo (
            correo     TEXT PRIMARY KEY,
            usuario_id INTEGER NOT NULL,
            creado_en  TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    \"\"\")
"""
assert s.count(bloque) == 1
open(p, "w", encoding="utf-8").write(s.replace(bloque, ""))
p = "almacen/servicio/almacen_bd.py"
s = open(p, encoding="utf-8").read()
ancla = """                CREATE TABLE IF NOT EXISTS cuotas (
                    usuario_id INTEGER PRIMARY KEY,
                    limite_bytes BIGINT NOT NULL
                );
"""
assert s.count(ancla) == 1
s = s.replace(ancla, ancla + """
                -- Vinculo explicito buzon -> persona del directorio central (lo fija el panel de
                -- administracion; manda sobre la coincidencia por correo). En todos los modos de directorio.
                CREATE TABLE IF NOT EXISTS enlaces_correo (
                    correo     TEXT PRIMARY KEY,
                    usuario_id INTEGER NOT NULL,
                    creado_en  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
""")
open(p, "w", encoding="utf-8").write(s)
print("DDL movido a almacen_bd.py")
