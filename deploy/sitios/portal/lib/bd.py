"""Consultas a la base del portal con `psql`, con el usuario panel_dominio y sus permisos mínimos.

Los valores van SIEMPRE como variables de psql (-v nombre=valor) y se usan en el SQL como :'nombre',
que psql cita como literal: nunca se pega texto de la petición dentro del SQL. Por eso el SQL entra
por la entrada estándar (en `-c` psql no sustituye variables).
"""

import json
import subprocess

import rutas
from errores import ErrorPortal


class FaltaTabla(Exception):
    """La consulta usa una tabla que este servidor todavía no tiene (esquema sin aplicar)."""


def entorno_portal(ruta=None):
    """PD_* de /etc/maquita-mail/panel-dominio.env (solo root lo lee)."""
    valores = {}
    try:
        with open(ruta or rutas.ENTORNO_PORTAL) as f:
            for linea in f:
                linea = linea.strip()
                if not linea or linea.startswith("#") or "=" not in linea:
                    continue
                clave, valor = linea.split("=", 1)
                valor = valor.strip()
                if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "'\"":
                    valor = valor[1:-1]
                valores[clave.strip()] = valor
    except OSError:
        raise ErrorPortal(503, "El portal de dominio no está configurado en este servidor")
    return valores


def _orden(env):
    return [rutas.PSQL, "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1",
            "-h", env.get("PD_DB_HOST", "127.0.0.1"), "-p", env.get("PD_DB_PORT", "5432"),
            "-U", env.get("PD_DB_USER", "panel_dominio"), "-d", env.get("PD_DB_NAME", "maildb")]


def consultar(sql, variables=None, tabla=None):
    """Ejecuta `sql` (que devuelve UNA columna JSON) y devuelve el valor de la primera fila, o None.

    `tabla`: si el error es que esa tabla no existe, lanza FaltaTabla (quien llama decide qué hacer)."""
    env = entorno_portal()
    orden = _orden(env)
    for nombre, valor in (variables or {}).items():
        orden += ["-v", f"{nombre}={valor}"]
    proc_env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PGCONNECT_TIMEOUT": "5",
                "PGPASSWORD": env.get("PD_DB_PASS", ""), "PGAPPNAME": "maquita-sitios-portal"}
    if env.get("PD_DB_SSL", "").lower() in ("1", "si", "require"):
        proc_env["PGSSLMODE"] = "require"
    try:
        r = subprocess.run(orden + ["-f", "-"], input=sql, capture_output=True, text=True, timeout=20,
                           env=proc_env, cwd="/")
    except (OSError, subprocess.TimeoutExpired):
        raise ErrorPortal(503, "No se pudo consultar la base del portal")
    if r.returncode != 0:
        if tabla and tabla in r.stderr and ("does not exist" in r.stderr or "no existe" in r.stderr):
            raise FaltaTabla(tabla)
        raise ErrorPortal(503, "No se pudo consultar la base del portal")
    texto = r.stdout.strip()
    if not texto:
        return None
    try:
        return json.loads(texto.splitlines()[0])
    except ValueError:
        raise ErrorPortal(503, "Respuesta no válida de la base del portal")
