"""Bases de datos adicionales de un sitio (MariaDB o PostgreSQL), para aplicaciones propias.

Cada base tiene su usuario propio que solo puede entrar desde este servidor (localhost) y solo a esa
base. La contraseña se muestra una vez. Al dar de baja el sitio se vuelcan y se borran con él.
"""

import os
import re
import secrets
import subprocess

from comun import ErrorSitio, clave, ejecutar, guardar_meta, leer_meta, slug, volcar

MOTORES = ("mariadb", "postgresql")


def _nombre(meta):
    return f"x_{slug(meta['dominio'])}_{secrets.token_hex(2)}"


def _pg(sql, base="postgres"):
    r = subprocess.run(["runuser", "-u", "postgres", "--", "psql", "-v", "ON_ERROR_STOP=1", "-q", "-d", base],
                       input=sql, capture_output=True, text=True, timeout=120, cwd="/tmp")
    if r.returncode != 0:
        raise ErrorSitio("PostgreSQL: " + (r.stderr.strip().splitlines() or ["error"])[-1][:300])


def listar(dominio):
    meta = leer_meta(dominio)
    return {"dominio": dominio, "bases": meta.get("bases", []), "principal": meta.get("bd")}


def crear(dominio, motor):
    if motor not in MOTORES:
        raise ErrorSitio("motor no válido")
    meta = leer_meta(dominio)
    if len(meta.get("bases", [])) >= 10:
        raise ErrorSitio("máximo 10 bases adicionales por sitio")
    nombre = _nombre(meta)
    contrasena = clave(24).replace("'", "")
    if motor == "mariadb":
        from aplicaciones import _mariadb

        _mariadb(f"CREATE DATABASE `{nombre}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
                 f"CREATE USER '{nombre}'@'localhost' IDENTIFIED BY '{contrasena}';"
                 f"GRANT ALL PRIVILEGES ON `{nombre}`.* TO '{nombre}'@'localhost'; FLUSH PRIVILEGES;")
        conexion = {"servidor": "localhost", "puerto": 3306}
    else:
        if not os.path.exists("/usr/bin/psql"):
            raise ErrorSitio("PostgreSQL no está instalado en este servidor")
        _pg(f"CREATE ROLE \"{nombre}\" LOGIN PASSWORD '{contrasena}';\n"
            f"CREATE DATABASE \"{nombre}\" OWNER \"{nombre}\" ENCODING 'UTF8' TEMPLATE template0;\n"
            f"REVOKE ALL ON DATABASE \"{nombre}\" FROM PUBLIC;\n")
        conexion = {"servidor": "127.0.0.1", "puerto": 5432}
    meta.setdefault("bases", []).append({"motor": motor, "nombre": nombre})
    guardar_meta(meta)
    return dict(conexion, dominio=dominio, motor=motor, base=nombre, usuario=nombre, clave=contrasena)


def borrar(dominio, nombre, volcar_en=None):
    meta = leer_meta(dominio)
    base = next((b for b in meta.get("bases", []) if b["nombre"] == nombre), None)
    if not base or not re.fullmatch(r"x_[a-z0-9]+_[0-9a-f]{4}", nombre):
        raise ErrorSitio("base de datos no encontrada")
    destino = volcar_en or os.path.join(meta["tmp"], f"{nombre}.sql")
    if base["motor"] == "mariadb":
        from aplicaciones import _mariadb

        volcar(["mariadb-dump", "--protocol=socket", "-u", "root", "--single-transaction", "--hex-blob", nombre], destino)
        _mariadb(f"DROP DATABASE IF EXISTS `{nombre}`; DROP USER IF EXISTS '{nombre}'@'localhost';")
    else:
        volcar(["runuser", "-u", "postgres", "--", "pg_dump", nombre], destino)
        _pg(f"DROP DATABASE IF EXISTS \"{nombre}\";\nDROP ROLE IF EXISTS \"{nombre}\";\n")
    if not volcar_en:
        # Que el dueño del sitio pueda descargar la copia por SFTP.
        ejecutar(["chown", f"{meta['usuario']}:{meta['usuario']}", destino])
    meta["bases"] = [b for b in meta.get("bases", []) if b["nombre"] != nombre]
    guardar_meta(meta)
    return {"dominio": dominio, "borrada": nombre, "copia": destino}


def borrar_todas(meta, carpeta):
    """Al dar de baja el sitio: cada base adicional se copia en la papelera y se borra."""
    for base in list(meta.get("bases", [])):
        borrar(meta["dominio"], base["nombre"], os.path.join(carpeta, f"{base['nombre']}.sql"))
