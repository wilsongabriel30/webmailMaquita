"""Privacidad de directorios: usuario y contraseña para entrar en una carpeta del sitio (autenticación básica).

Las claves (cifradas con bcrypt, o apr1 si no hay htpasswd) quedan en la carpeta privada del sitio, fuera de la
pública y fuera del alcance de su usuario de FTP:

    /srv/sitios/<dominio>/claves-carpetas/            root:www-data 750
    /srv/sitios/<dominio>/claves-carpetas/<id>.htpasswd   root:www-data 640   (una por carpeta)

nginx lo aplica a nivel de server{} con variables (auth_basic $sitio_privado), no con una location por carpeta:
así los .php de la carpeta siguen pasando por PHP-FPM y las reglas que prohíben archivos ocultos y copias siguen
valiendo dentro. La contraseña se devuelve una sola vez (si la genera el ayudante) y no se guarda en claro.
"""

import hashlib
import os
import re
import shutil
import subprocess

import web_comun as w
from comun import ErrorSitio, clave, leer_meta

CARPETA = "claves-carpetas"
HTPASSWD = "/usr/bin/htpasswd"
OPENSSL = "/usr/bin/openssl"
GRUPO_WEB = "www-data"
MAX_CARPETAS = 20
MAX_USUARIOS = 50
RE_USUARIO = re.compile(r"^[A-Za-z0-9._-]{1,32}$")
RE_REINO = re.compile(r"^[A-Za-z0-9 áéíóúÁÉÍÓÚñÑüÜ.,()-]{1,60}$")
REINO = "Zona privada"


def _carpeta(meta):
    return os.path.join(meta["base"], CARPETA)


def ruta_claves(meta, ruta):
    return os.path.join(_carpeta(meta), hashlib.sha256(ruta.encode()).hexdigest()[:16] + ".htpasswd")


def usuario(valor):
    if not isinstance(valor, str) or not RE_USUARIO.fullmatch(valor):
        raise ErrorSitio("usuario no válido (letras sin tilde, números y . _ -, hasta 32)")
    return valor


def _clave_propia(valor):
    if not isinstance(valor, str) or not 8 <= len(valor) <= 128 or re.search(r"[\x00-\x1f\x7f:]", valor):
        raise ErrorSitio("la contraseña debe tener entre 8 y 128 caracteres, sin «:» ni caracteres de control")
    return valor


def _cifrar(nombre, secreto):
    """Línea «usuario:hash». bcrypt con htpasswd (apache2-utils); si no está, apr1 con openssl. La contraseña va por
    la entrada estándar, nunca como argumento (se vería en la lista de procesos)."""
    if os.path.exists(HTPASSWD):
        r = subprocess.run([HTPASSWD, "-niB", "-C", "10", nombre], input=secreto + "\n", capture_output=True,
                           text=True, timeout=30)
        if r.returncode == 0 and r.stdout.startswith(nombre + ":$2"):
            return r.stdout.strip()
    r = subprocess.run([OPENSSL, "passwd", "-apr1", "-stdin"], input=secreto + "\n", capture_output=True, text=True,
                       timeout=30)
    if r.returncode != 0 or not r.stdout.startswith("$apr1$"):
        raise ErrorSitio("no se pudo cifrar la contraseña")
    return f"{nombre}:{r.stdout.strip()}"


def _leer(ruta):
    try:
        with open(ruta) as f:
            return [l.rstrip("\n") for l in f if ":" in l]
    except FileNotFoundError:
        return []


def _escribir_claves(meta, ruta, lineas):
    os.makedirs(_carpeta(meta), mode=0o750, exist_ok=True)
    tmp = ruta + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o640), "w") as f:
        f.write("".join(l + "\n" for l in lineas))
    if os.geteuid() == 0:
        import grp

        gid = grp.getgrnam(GRUPO_WEB).gr_gid
        os.chown(_carpeta(meta), 0, gid)
        os.chmod(_carpeta(meta), 0o750)
        os.chown(tmp, 0, gid)
    os.chmod(tmp, 0o640)
    os.replace(tmp, ruta)


def validar(meta, datos):
    """Lista [{"ruta", "nombre", "usuarios"}] (sin contraseñas: esas solo están en los .htpasswd)."""
    limpias, vistas = [], set()
    for c in w.lista(datos, MAX_CARPETAS, "carpetas privadas"):
        if not isinstance(c, dict):
            raise ErrorSitio("carpeta privada no válida")
        ruta = w.ruta(c.get("ruta"), "carpeta")
        if ruta == "/" or ruta.startswith("/.well-known"):
            raise ErrorSitio("esa carpeta no se puede proteger (para todo el sitio, proteja una subcarpeta)")
        reino = str(c.get("nombre") or REINO)
        if not RE_REINO.fullmatch(reino):
            raise ErrorSitio("el nombre de la zona solo lleva letras, números, espacios y . , ( ) -")
        usuarios = [usuario(u) for u in w.lista(c.get("usuarios"), MAX_USUARIOS, "usuarios de la carpeta")]
        if ruta in vistas:
            raise ErrorSitio(f"la carpeta {ruta} está repetida")
        vistas.add(ruta)
        limpias.append({"ruta": ruta, "nombre": reino, "usuarios": sorted(set(usuarios))})
    return limpias


def fragmentos(meta, ajustes):
    carpetas = [c for c in validar(meta, ajustes) if c["usuarios"]] if ajustes else []
    if not carpetas:
        return {}
    lineas = ["# Carpetas con usuario y contraseña", "set $sitio_privado off;", "set $sitio_claves /dev/null;"]
    # De la más corta a la más larga: si hay carpetas anidadas, manda la más interior.
    for c in sorted(carpetas, key=lambda c: len(c["ruta"])):
        lineas.append(f'if ($uri ~ "^{w.regex(c["ruta"])}(?:/|$)") {{ set $sitio_privado "{c["nombre"]}"; '
                      f'set $sitio_claves "{ruta_claves(meta, c["ruta"])}"; }}')
    lineas += ["auth_basic $sitio_privado;", "auth_basic_user_file $sitio_claves;"]
    return {"servidor": "\n".join(lineas)}


def estado(meta, ajustes):
    return {"carpetas": ajustes or [], "maximo": MAX_CARPETAS}


# --- Órdenes ---


def agregar(dominio, ruta, nombre, secreto=None, reino=None):
    """Añade un usuario a la carpeta (la protege si aún no lo estaba) o le cambia la contraseña."""
    import nginx_web

    meta = leer_meta(dominio)
    ruta = w.ruta(ruta, "carpeta")
    nombre = usuario(nombre)
    generada = secreto is None
    secreto = clave(16) if generada else _clave_propia(secreto)
    carpetas = validar(meta, (meta.get("web") or {}).get("privacidad"))
    actual = next((c for c in carpetas if c["ruta"] == ruta), None)
    if not actual:
        actual = {"ruta": ruta, "nombre": reino or REINO, "usuarios": []}
        carpetas.append(actual)
    elif reino:
        actual["nombre"] = reino
    if nombre not in actual["usuarios"] and len(actual["usuarios"]) >= MAX_USUARIOS:
        raise ErrorSitio(f"como máximo {MAX_USUARIOS} usuarios por carpeta")
    actual["usuarios"] = sorted(set(actual["usuarios"]) | {nombre})
    carpetas = validar(meta, carpetas)
    archivo = ruta_claves(meta, ruta)
    linea = _cifrar(nombre, secreto)

    def preparar(_nuevo):
        _escribir_claves(meta, archivo, [l for l in _leer(archivo) if l.split(":", 1)[0] != nombre] + [linea])

    nginx_web.aplicar(dominio, "privacidad", carpetas, extra_rutas=[archivo], preparar=preparar)
    salida = {**nginx_web.ver(dominio), "carpeta": ruta, "usuario": nombre}
    if generada:
        salida["clave"] = secreto  # una sola vez: no se guarda en claro en ningún sitio
    return salida


def quitar(dominio, ruta, nombre=None):
    """Quita un usuario de la carpeta, o la protección entera si no se indica usuario (o era el último)."""
    import nginx_web

    meta = leer_meta(dominio)
    ruta = w.ruta(ruta, "carpeta")
    carpetas = validar(meta, (meta.get("web") or {}).get("privacidad"))
    actual = next((c for c in carpetas if c["ruta"] == ruta), None)
    if not actual:
        raise ErrorSitio(f"{ruta} no está protegida")
    if nombre is not None:
        nombre = usuario(nombre)
        if nombre not in actual["usuarios"]:
            raise ErrorSitio(f"{nombre} no tiene acceso a {ruta}")
        actual["usuarios"].remove(nombre)
    if nombre is None or not actual["usuarios"]:
        carpetas.remove(actual)
    archivo = ruta_claves(meta, ruta)
    queda = actual in carpetas

    def preparar(_nuevo):
        if queda:
            _escribir_claves(meta, archivo, [l for l in _leer(archivo) if l.split(":", 1)[0] != nombre])

    nginx_web.aplicar(dominio, "privacidad", carpetas or None, extra_rutas=[archivo], preparar=preparar)
    if not queda and os.path.exists(archivo):
        os.remove(archivo)  # nginx ya no la usa
    if not carpetas:
        shutil.rmtree(_carpeta(meta), ignore_errors=True)
    return nginx_web.ver(dominio)
