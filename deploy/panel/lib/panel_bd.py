"""Base de datos y entorno para las órdenes de consola del panel (maquita-panel, maquita-panel-dominio).

Corren como root en el servidor y entran a la base con las credenciales del panel general
(admin-panel/backend/.env: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS), que es el dueño de las
tablas del panel y de las del portal de dominio. Como en el intermediario de los sitios, los
valores van SIEMPRE como variables de psql (-v nombre=valor) y en el SQL como :'nombre': nunca se
pega texto de la orden dentro del SQL, que entra por la entrada estándar.
"""

import json
import os
import socket
import subprocess

APP = os.environ.get("MAQUITA_APP", "/opt/maquita-webmail")
ENTORNO_PANEL = os.path.join(APP, "admin-panel/backend/.env")
ENTORNO_CORREO = os.path.join(APP, "backend/.env")
ORGANIZACION = os.environ.get("ORG_FICHERO", "/etc/maquita-mail/organizacion.env")
PSQL = "/usr/bin/psql"


class ErrorConsola(Exception):
    """Error que se le explica a la persona (sale con código 1)."""


class FaltaTabla(ErrorConsola):
    pass


def opciones(args, permitidas, banderas=()):
    """Separa posicionales y opciones (--vida N, --host X, --json). Rechaza lo desconocido."""
    posicionales, opciones = [], {}
    i = 0
    while i < len(args):
        a = args[i]
        if a in banderas:
            opciones[a] = True
        elif a in permitidas:
            if i + 1 >= len(args):
                raise ErrorConsola(f"falta el valor de {a}")
            opciones[a] = args[i + 1]
            i += 1
        elif a.startswith("--"):
            raise ErrorConsola(f"opción desconocida: {a}")
        else:
            posicionales.append(a)
        i += 1
    return posicionales, opciones


def leer_entorno(ruta):
    """CLAVE=valor de un archivo .env (sin shell). {} si no existe o no se puede leer."""
    valores = {}
    try:
        with open(ruta, encoding="utf-8") as f:
            for linea in f:
                linea = linea.strip()
                if not linea or linea.startswith("#") or "=" not in linea:
                    continue
                clave, valor = linea.split("=", 1)
                clave = clave.strip().removeprefix("export ").strip()
                valor = valor.strip()
                if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "'\"":
                    valor = valor[1:-1]
                valores[clave] = valor
    except OSError:
        pass
    return valores


def consultar(sql, variables=None, tabla=None):
    """Ejecuta `sql` (que devuelve UNA columna JSON) y devuelve el valor de la primera fila, o None."""
    env = leer_entorno(ENTORNO_PANEL)
    if not env.get("DB_PASS"):
        raise ErrorConsola(f"no se pudo leer la conexión a la base en {ENTORNO_PANEL} (¿se ejecuta como root?)")
    orden = [PSQL, "-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1",
             "-h", env.get("DB_HOST", "localhost"), "-p", env.get("DB_PORT", "5432"),
             "-U", env.get("DB_USER", "mailserver"), "-d", env.get("DB_NAME", "maildb")]
    for nombre, valor in (variables or {}).items():
        orden += ["-v", f"{nombre}={valor}"]
    proc_env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PGCONNECT_TIMEOUT": "5",
                "PGPASSWORD": env["DB_PASS"], "PGAPPNAME": "maquita-panel-consola"}
    try:
        r = subprocess.run(orden + ["-f", "-"], input=sql, capture_output=True, text=True, timeout=30,
                           env=proc_env, cwd="/")
    except (OSError, subprocess.TimeoutExpired):
        raise ErrorConsola("no se pudo consultar la base de datos")
    if r.returncode != 0:
        if tabla and tabla in r.stderr and ("does not exist" in r.stderr or "no existe" in r.stderr):
            raise FaltaTabla(f"falta la tabla {tabla}: aplique el ajuste 66 (deploy/ajustes/aplicar-ajustes.sh --aplicar)")
        raise ErrorConsola("la base de datos rechazó la operación: " + (r.stderr.strip().splitlines() or ["?"])[-1][:200])
    texto = r.stdout.strip()
    if not texto:
        return None
    try:
        return json.loads(texto.splitlines()[0])
    except ValueError:
        raise ErrorConsola("respuesta no válida de la base de datos")


def valor_org(clave):
    """Un valor de la organización: el entorno, después organizacion.env."""
    return os.environ.get(clave) or leer_entorno(ORGANIZACION).get(clave, "")


def servidor_correo():
    """MAIL_HOST del correo (backend/.env), el nombre por el que se entra al panel y al portal. Sin él, el nombre
    completo del servidor (hostname -f), que en una instalación normal es el del correo."""
    nombre = leer_entorno(ENTORNO_CORREO).get("MAIL_HOST", "").strip().lower()
    if not nombre:
        completo = socket.getfqdn().strip().lower()
        nombre = completo if "." in completo and completo != "localhost.localdomain" else ""
    return nombre
