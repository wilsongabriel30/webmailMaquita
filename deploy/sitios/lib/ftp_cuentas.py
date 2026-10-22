"""Cuentas FTP adicionales de un sitio: otra persona (un diseñador, un proveedor) entra solo en una subcarpeta.

Mismo modelo de seguridad que la cuenta principal (acceso.py): FTP solo con cifrado (vsftpd, lista
/etc/vsftpd.sitios) y SFTP sin shell (grupo «sitios», ChrootDirectory %h en sshd_config). Lo que cambia es el
encierro: sshd exige que la raíz del encierro y todas sus carpetas de arriba sean de root, y la carpeta pública es
del usuario del sitio. Por eso cada cuenta tiene su raíz propia, de root, fuera de la carpeta del sitio (así no
cuenta dos veces en el espacio ni en los respaldos), y dentro una carpeta «archivos» montada (bind) sobre la
subcarpeta elegida:

    /srv/sitios-ftp/<dominio>/<cuenta>/            root:root 755   (raíz del FTP/SFTP de la cuenta)
    /srv/sitios-ftp/<dominio>/<cuenta>/archivos/   → /srv/sitios/<dominio>/publico/<subcarpeta>

La cuenta usa el mismo UID y grupo que el usuario del sitio (useradd -o): lo que sube es del sitio, PHP lo puede
leer y la cuenta principal lo puede cambiar, como si lo hubiera subido ella. Tiene su propia contraseña y se da de
baja sola. La subcarpeta se abre componente a componente sin seguir enlaces simbólicos y se monta desde ese
descriptor: el usuario del sitio no puede cambiarla por un enlace a otra parte del sistema, ni al crearla ni al
volver a montarla tras reiniciar (sitios-ftp-montar.service → «maquita-sitios ftp-montar»).
"""

import os
import pwd
import re
import subprocess
import time

from comun import GRUPO_SITIOS, ErrorSitio, clave, ejecutar, guardar_meta, leer_meta, todos_los_meta

RAIZ_FTP = "/srv/sitios-ftp"
MONTAJES = "/proc/self/mountinfo"
MOUNT = "/usr/bin/mount"
UMOUNT = "/usr/bin/umount"
MAXIMO = 10
RE_NOMBRE = re.compile(r"^[a-z][a-z0-9]{1,10}$")
RE_PARTE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]{0,63}$")


def nombre(valor):
    if not isinstance(valor, str) or not RE_NOMBRE.fullmatch(valor):
        raise ErrorSitio("nombre de cuenta no válido (2 a 11 minúsculas o números, empezando por letra)")
    return valor


def subcarpeta(valor):
    """Ruta relativa a la carpeta pública: «imagenes» o «tienda/catalogo». Sin «..» ni carpetas ocultas."""
    valor = str(valor or "").strip().strip("/")
    partes = valor.split("/")
    if not valor or len(partes) > 5 or len(valor) > 200 or not all(RE_PARTE.fullmatch(p) for p in partes):
        raise ErrorSitio("subcarpeta no válida (dentro de la carpeta pública, sin «..» ni carpetas ocultas)")
    return valor


def usuario_sistema(meta, cuenta):
    # «ana_ejemplo1234»: el nombre de la cuenta y el identificador del sitio (como mucho 28 caracteres).
    return f"{cuenta}_{meta['usuario'].removeprefix('web')}"


def raiz(meta, cuenta):
    return os.path.join(RAIZ_FTP, meta["dominio"], cuenta)


def montaje(meta, cuenta):
    return os.path.join(raiz(meta, cuenta), "archivos")


# --- Montaje sin enlaces simbólicos ---


def _abrir(meta, relativa):
    """Descriptor de la subcarpeta, abierta componente a componente con O_NOFOLLOW desde la carpeta pública."""
    banderas = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(meta["publico"], banderas)
    try:
        for parte in relativa.split("/"):
            siguiente = os.open(parte, banderas, dir_fd=fd)
            os.close(fd)
            fd = siguiente
    except FileNotFoundError:
        os.close(fd)
        raise ErrorSitio(f"no existe la carpeta publico/{relativa}: créela primero (por FTP o SFTP)")
    except (NotADirectoryError, OSError):
        os.close(fd)
        raise ErrorSitio(f"publico/{relativa} no es una carpeta (o es un enlace simbólico)")
    return fd


def _montado(destino):
    try:
        with open(MONTAJES) as f:
            for linea in f:
                campos = linea.split()
                if len(campos) > 4 and campos[4].encode().decode("unicode_escape") == destino:
                    return True
    except OSError:
        pass
    return False


def _montar(meta, cuenta):
    destino = montaje(meta, cuenta)
    if _montado(destino):
        return
    fd = _abrir(meta, cuenta_de(meta, cuenta)["carpeta"])
    try:
        # --no-canonicalize: mount no resuelve la ruta; el núcleo monta exactamente la carpeta del descriptor.
        r = subprocess.run([MOUNT, "--no-canonicalize", "--bind", f"/proc/self/fd/{fd}", destino],
                           pass_fds=(fd,), capture_output=True, text=True, timeout=30)
    finally:
        os.close(fd)
    if r.returncode != 0:
        raise ErrorSitio("no se pudo montar la carpeta de la cuenta: " + (r.stderr.strip().splitlines() or ["?"])[-1][:200])
    ejecutar([MOUNT, "--no-canonicalize", "-o", "remount,bind,nosuid,nodev,noexec", destino])


def _desmontar(destino):
    if _montado(destino):
        # Diferido (-l): si alguien tiene una sesión abierta dentro, se desengancha igual.
        ejecutar([UMOUNT, "-l", destino])


def _quitar_carpetas(meta, cuenta):
    """Solo rmdir, nunca un borrado recursivo: si el montaje siguiera ahí, se borrarían los archivos del sitio."""
    for ruta in (montaje(meta, cuenta), raiz(meta, cuenta), os.path.join(RAIZ_FTP, meta["dominio"])):
        try:
            os.rmdir(ruta)
        except OSError:
            pass


# --- Órdenes ---


def cuenta_de(meta, cuenta):
    c = next((c for c in meta.get("ftp_cuentas", []) if c["nombre"] == cuenta), None)
    if not c:
        raise ErrorSitio(f"la cuenta {cuenta} no existe en {meta['dominio']}")
    return c


def _publica(meta, c):
    return {"nombre": c["nombre"], "usuario": c["usuario"], "carpeta": c["carpeta"], "creada": c.get("creada"),
            "montada": _montado(montaje(meta, c["nombre"]))}


def listar(dominio):
    meta = leer_meta(dominio)
    return {"dominio": dominio, "maximo": MAXIMO, "carpeta_web": "archivos",
            "cuentas": [_publica(meta, c) for c in meta.get("ftp_cuentas", [])]}


def crear(dominio, cuenta, carpeta):
    import acceso

    meta = leer_meta(dominio)
    cuenta, carpeta = nombre(cuenta), subcarpeta(carpeta)
    cuentas = meta.setdefault("ftp_cuentas", [])
    if any(c["nombre"] == cuenta for c in cuentas):
        raise ErrorSitio(f"la cuenta {cuenta} ya existe")
    if len(cuentas) >= MAXIMO:
        raise ErrorSitio(f"como máximo {MAXIMO} cuentas FTP adicionales por sitio")
    os.close(_abrir(meta, carpeta))  # que exista y no sea un enlace, antes de crear nada
    usuario = usuario_sistema(meta, cuenta)
    try:
        pwd.getpwnam(usuario)
        raise ErrorSitio(f"el usuario de sistema {usuario} ya existe")
    except KeyError:
        pass
    sitio = pwd.getpwnam(meta["usuario"])
    for ruta in (RAIZ_FTP, os.path.join(RAIZ_FTP, dominio), raiz(meta, cuenta), montaje(meta, cuenta)):
        os.makedirs(ruta, mode=0o755, exist_ok=True)
        os.chown(ruta, 0, 0)
        os.chmod(ruta, 0o755)
    ejecutar(["useradd", "--system", "--no-create-home", "--home-dir", raiz(meta, cuenta), "--shell", "/usr/sbin/nologin",
              "--non-unique", "--uid", str(sitio.pw_uid), "--gid", str(sitio.pw_gid), "--groups", GRUPO_SITIOS, usuario])
    entrada = {"nombre": cuenta, "usuario": usuario, "carpeta": carpeta, "creada": time.strftime("%Y-%m-%d %H:%M")}
    cuentas.append(entrada)
    try:
        _montar(meta, cuenta)
        nueva = clave(16)
        ejecutar(["chpasswd"], entrada=f"{usuario}:{nueva}\n")
        acceso._guardar_lista(acceso._lista() + [usuario])
    except ErrorSitio:
        _baja(meta, entrada)
        raise
    guardar_meta(meta)
    return {**listar(dominio), "cuenta": _publica(meta, entrada), "usuario": usuario, "clave": nueva,
            "carpeta_web": "archivos"}


def nueva_clave(dominio, cuenta):
    meta = leer_meta(dominio)
    c = cuenta_de(meta, nombre(cuenta))
    nueva = clave(16)
    ejecutar(["chpasswd"], entrada=f"{c['usuario']}:{nueva}\n")
    return {**listar(dominio), "usuario": c["usuario"], "clave": nueva, "carpeta_web": "archivos"}


def _baja(meta, c):
    import acceso

    acceso.quitar_de_lista_ftp(c["usuario"])
    try:
        ejecutar(["passwd", "-l", c["usuario"]])
    except ErrorSitio:
        pass
    _desmontar(montaje(meta, c["nombre"]))
    try:
        # -f: userdel cree que la cuenta está «en uso» por los procesos de PHP del sitio (mismo UID). Sin -r: su
        # carpeta es la raíz del encierro, que se quita aparte y solo si está vacía.
        ejecutar(["userdel", "-f", c["usuario"]])
    except ErrorSitio:
        pass
    _quitar_carpetas(meta, c["nombre"])
    import claves_ssh

    claves_ssh.quitar_cuenta(meta, c["nombre"], c["usuario"])  # sus claves SSH dejan de valer con ella
    meta["ftp_cuentas"] = [x for x in meta.get("ftp_cuentas", []) if x["nombre"] != c["nombre"]]


def quitar(dominio, cuenta):
    meta = leer_meta(dominio)
    c = cuenta_de(meta, nombre(cuenta))
    _baja(meta, c)
    if _montado(montaje(meta, c["nombre"])):
        raise ErrorSitio("no se pudo desmontar la carpeta de la cuenta; vuelva a intentarlo")
    guardar_meta(meta)
    return listar(dominio)


def quitar_todas(meta):
    """Al dar de baja el sitio (antes de mover su carpeta a la papelera)."""
    for c in list(meta.get("ftp_cuentas", [])):
        _baja(meta, c)
    if meta.get("ftp_cuentas") == []:
        meta.pop("ftp_cuentas")


def montar_todas():
    """Al arrancar el servidor: vuelve a montar las carpetas de todas las cuentas adicionales."""
    hechas, fallidas = [], []
    for meta in todos_los_meta():
        for c in meta.get("ftp_cuentas", []):
            try:
                _montar(meta, c["nombre"])
                hechas.append(c["usuario"])
            except (ErrorSitio, OSError) as e:
                fallidas.append({"usuario": c["usuario"], "motivo": str(e)[:200]})
    return {"montadas": hechas, "fallidas": fallidas}
