"""La conexión con el portal: quién llama (SO_PEERCRED) y una línea JSON de ida y otra de vuelta.

systemd acepta la conexión (Accept=yes) y arranca una instancia por cliente con el socket como entrada
y salida estándar. El usuario del otro extremo lo da el núcleo, no el cliente: no se puede falsear.
"""

import json
import os
import pwd
import socket
import struct

import rutas
from errores import ErrorPortal

MAXIMO = 64 * 1024


def usuario_del_par(fd=0):
    """uid del proceso conectado al socket `fd` (por defecto, la entrada estándar)."""
    s = socket.socket(fileno=os.dup(fd))
    try:
        datos = s.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    finally:
        s.close()
    _pid, uid, _gid = struct.unpack("3i", datos)
    return uid


def par_autorizado(uid):
    """Solo el usuario del portal, o root (pruebas a mano en el propio servidor)."""
    if uid == 0:
        return True
    try:
        return uid == pwd.getpwnam(rutas.USUARIO_PORTAL).pw_uid
    except KeyError:
        return False


def leer_peticion(entrada):
    """Lee UNA línea (máx. 64 KB) de un archivo binario y la devuelve como dict."""
    linea = entrada.readline(MAXIMO + 1)
    if len(linea) > MAXIMO:
        raise ErrorPortal(413, "La petición es demasiado grande")
    try:
        peticion = json.loads(linea.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ErrorPortal(400, "Petición no válida")
    if not isinstance(peticion, dict):
        raise ErrorPortal(400, "Petición no válida")
    return peticion


def responder(salida, respuesta):
    salida.write(json.dumps(respuesta, ensure_ascii=False).encode("utf-8") + b"\n")
    salida.flush()


def error(e):
    return {"ok": False, "codigo": e.codigo, "error": e.texto}
