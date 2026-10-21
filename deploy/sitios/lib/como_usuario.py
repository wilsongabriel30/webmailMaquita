"""Ejecutar una función con el usuario del sitio (no como root).

El administrador de archivos y la descompresión trabajan dentro de la carpeta del sitio, que controla su dueño
(por SFTP o desde su aplicación). Si lo hiciera root, un enlace simbólico puesto a tiempo bastaría para leer o
pisar archivos del sistema, y lo creado quedaría de root. Por eso la operación corre en un proceso hijo que
deja los privilegios (setgroups, setgid, setuid) antes de tocar nada: el núcleo le niega lo que el usuario del
sitio no podría hacer por sí mismo. La comprobación de rutas (archivos_rutas.py) es una segunda barrera.

Los descriptores abiertos por root antes de bifurcar (la subida que dejó el panel, el archivo de descarga en
subidas/) se heredan: así el hijo lee o escribe en ellos sin tener permiso sobre esas carpetas.
"""

import json
import os
import pwd
import signal

from comun import ErrorSitio

# Las pruebas (sin root) lo ponen a False: la función corre en el mismo proceso.
CAMBIAR_USUARIO = True
TIEMPO = 1700  # segundos; el panel espera como mucho 1800


def ejecutar_como(usuario, funcion, *args, tiempo=TIEMPO):
    """Devuelve lo que devuelve `funcion(*args)` (algo serializable en JSON) o lanza ErrorSitio."""
    if not CAMBIAR_USUARIO:
        return funcion(*args)
    pw = pwd.getpwnam(usuario)
    if pw.pw_uid == 0:
        raise ErrorSitio("el usuario del sitio no puede ser root")
    lectura, escritura = os.pipe()
    pid = os.fork()
    if pid == 0:  # hijo
        codigo = 0
        try:
            os.close(lectura)
            # Solo su propio grupo: «www-data» no, que puede leer las carpetas públicas de los demás sitios.
            os.setgroups([pw.pw_gid])
            os.setgid(pw.pw_gid)
            os.setuid(pw.pw_uid)
            os.umask(0o027)
            os.environ["HOME"] = "/tmp"
            signal.alarm(tiempo)
            salida = {"ok": funcion(*args)}
        except ErrorSitio as e:
            salida = {"error": str(e)}
        except PermissionError:
            salida = {"error": "permiso denegado: el usuario del sitio no puede hacer eso"}
        except FileNotFoundError:
            salida = {"error": "no existe (puede que se haya movido o borrado mientras tanto)"}
        except BaseException as e:  # noqa: BLE001  el hijo nunca debe volver al código del padre
            salida = {"fallo": f"{type(e).__name__}: {e}"[:300]}
            codigo = 1
        try:
            datos = json.dumps(salida, ensure_ascii=False).encode()
            while datos:
                datos = datos[os.write(escritura, datos):]
        finally:
            os._exit(codigo)
    os.close(escritura)
    partes = []
    with os.fdopen(lectura, "rb") as f:
        while bloque := f.read(1 << 16):
            partes.append(bloque)
    os.waitpid(pid, 0)
    try:
        salida = json.loads(b"".join(partes) or b"{}")
    except ValueError:
        salida = {}
    if "ok" in salida:
        return salida["ok"]
    if "error" in salida:
        raise ErrorSitio(salida["error"])
    raise ErrorSitio("la operación con el usuario del sitio no terminó" + (f" ({salida['fallo']})" if salida.get("fallo") else ""))
