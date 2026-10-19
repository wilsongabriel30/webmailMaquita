"""Migración desde otro hosting: los archivos del sitio (.zip/.tar.gz) y el respaldo de su base (.sql o .sql.gz).

La base se importa con el usuario propio del sitio, que solo entra a su base: un respaldo con «USE otra_base»,
«CREATE DATABASE» o DEFINER de otro usuario no puede tocar nada más (esas líneas se quitan antes; las de
DEFINER fallarían sin privilegios). Después se reconoce la aplicación y se le pone la conexión nueva:
- WordPress (wp-config.php): base, usuario, clave y servidor; si cambió el dominio, se reemplaza la dirección
  vieja por la nueva en toda la base (wp search-replace, respeta los datos serializados).
- Joomla (configuration.php): conexión, rutas de registros y temporales, y dirección.
- Laravel y similares (.env): DB_HOST, DB_DATABASE, DB_USERNAME, DB_PASSWORD.
Si no se reconoce, el panel muestra los datos de la base para ponerlos a mano.
"""

import gzip
import os
import re
import subprocess
import tempfile

from comun import ErrorSitio, ejecutar

RE_BASE = re.compile(r"^[0-9a-f]{32}\.(sql|sql\.gz)$")
RE_DEFINER = re.compile(rb"(/\*!\d+\s+)?DEFINER\s*=\s*(`[^`]*`|'[^']*'|\S+)@(`[^`]*`|'[^']*'|\S+)(\s*\*/)?\s*", re.I)
RE_FUERA = re.compile(rb"^\s*(CREATE\s+DATABASE|USE\s+)", re.I)


def _lineas(ruta):
    abrir = gzip.open if ruta.endswith(".gz") else open
    try:
        with abrir(ruta, "rb") as f:
            for linea in f:
                if RE_FUERA.match(linea):
                    continue
                yield RE_DEFINER.sub(b"", linea)
    except (OSError, EOFError) as e:
        raise ErrorSitio(f"no se pudo leer el respaldo de la base: {e}")


def importar(meta, ruta, bd, usuario, clave):
    """Importa el respaldo en la base del sitio con el usuario del sitio."""
    with tempfile.NamedTemporaryFile("w", dir=meta["tmp"], prefix=".bd-", suffix=".cnf", delete=False) as cnf:
        cnf.write(f"[client]\nuser={usuario}\npassword=\"{clave}\"\nprotocol=socket\n")
    os.chmod(cnf.name, 0o600)
    try:
        proc = subprocess.Popen(["mariadb", f"--defaults-extra-file={cnf.name}", "--max-allowed-packet=256M",
                                 "--default-character-set=utf8mb4", bd], stdin=subprocess.PIPE,
                                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, cwd="/tmp")
        try:
            for linea in _lineas(ruta):
                proc.stdin.write(linea)
            proc.stdin.close()
        except BrokenPipeError:
            pass
        error = proc.stderr.read().decode(errors="replace").strip()
        if proc.wait(timeout=3600) != 0:
            raise ErrorSitio("la base no se pudo importar: " + (error.splitlines()[-1][:300] if error else "error de MariaDB"))
    finally:
        os.remove(cnf.name)
    tablas = subprocess.run(["mariadb", "--protocol=socket", "-u", "root", "-N", "-e",
                             f"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='{bd}'"],
                            capture_output=True, text=True, timeout=60).stdout.strip()
    return int(tablas or 0)


def _reemplazar(ruta, cambios):
    with open(ruta, encoding="utf-8", errors="surrogateescape") as f:
        texto = f.read()
    for patron, valor in cambios:
        texto, n = re.subn(patron, lambda m: m.group(1) + valor + m.group(2), texto, count=1, flags=re.M)
    with open(ruta, "w", encoding="utf-8", errors="surrogateescape") as f:
        f.write(texto)


def _php_cadena(valor):
    return valor.replace("\\", "\\\\").replace("'", "\\'")


def _wordpress(meta, raiz, bd, usuario, clave):
    from aplicaciones import _wp

    for nombre, valor in (("DB_NAME", bd), ("DB_USER", usuario), ("DB_PASSWORD", clave), ("DB_HOST", "localhost")):
        _wp(meta, "config", "set", nombre, valor, "--type=constant")
    nueva = ("https://" if meta.get("ssl") else "http://") + meta["dominio"]
    vieja = _wp(meta, "option", "get", "siteurl", "--skip-plugins", "--skip-themes").strip().rstrip("/")
    reemplazos = 0
    if vieja and vieja != nueva:
        salida = _wp(meta, "search-replace", vieja, nueva, "--all-tables-with-prefix", "--skip-columns=guid",
                     "--skip-plugins", "--skip-themes", "--format=count")
        reemplazos = int(salida.strip() or 0) if salida.strip().isdigit() else 0
        # La dirección sin «www.» o con el otro esquema también aparece a menudo en los contenidos.
        for variante in {vieja.replace("://www.", "://"), vieja.replace("https://", "http://"),
                         vieja.replace("http://", "https://")} - {vieja, nueva}:
            _wp(meta, "search-replace", variante, nueva, "--all-tables-with-prefix", "--skip-columns=guid",
                "--skip-plugins", "--skip-themes", "--format=count")
    administradores = _wp(meta, "user", "list", "--role=administrator", "--field=user_login",
                          "--skip-plugins", "--skip-themes").split()
    _wp(meta, "cache", "flush", "--skip-plugins", "--skip-themes")
    return {"aplicacion": "wordpress", "direccion_anterior": vieja, "reemplazos": reemplazos,
            "admin_usuario": administradores[0] if administradores else None}


def _joomla(meta, raiz, bd, usuario, clave):
    ruta = os.path.join(raiz, "configuration.php")
    nueva = ("https://" if meta.get("ssl") else "http://") + meta["dominio"]
    cambios = [(r"(public \$%s\s*=\s*')[^']*(';)" % campo, _php_cadena(valor)) for campo, valor in
               (("host", "localhost"), ("user", usuario), ("password", clave), ("db", bd), ("dbtype", "mysqli"),
                ("log_path", os.path.join(meta["tmp"], "joomla-registros")),
                ("tmp_path", os.path.join(meta["tmp"], "joomla-temporales")), ("live_site", ""))]
    _reemplazar(ruta, cambios)
    for carpeta in ("joomla-registros", "joomla-temporales"):
        from apps.receta import privada

        privada(meta, carpeta)
    return {"aplicacion": "joomla", "direccion_nueva": nueva}


def _env(meta, raiz, bd, usuario, clave):
    ruta = next(os.path.join(d, ".env") for d in (raiz, meta["publico"]) if os.path.isfile(os.path.join(d, ".env")))
    with open(ruta) as f:
        texto = f.read()
    for clave_env, valor in (("DB_HOST", "localhost"), ("DB_DATABASE", bd), ("DB_USERNAME", usuario), ("DB_PASSWORD", clave),
                             ("DB_CONNECTION", "mysql")):
        if re.search(rf"^{clave_env}=", texto, re.M):
            texto = re.sub(rf"^{clave_env}=.*$", f"{clave_env}={valor}", texto, count=1, flags=re.M)
        else:
            texto += f"\n{clave_env}={valor}"
    nueva = ("https://" if meta.get("ssl") else "http://") + meta["dominio"]
    texto = re.sub(r"^APP_URL=.*$", f"APP_URL={nueva}", texto, count=1, flags=re.M)
    with open(ruta, "w") as f:
        f.write(texto)
    return {"aplicacion": "env"}


def conectar(meta, raiz_web, bd, usuario, clave):
    """Reconoce la aplicación subida y le pone la conexión a la base nueva. Devuelve qué se hizo."""
    raiz = os.path.join(meta["publico"], raiz_web) if raiz_web else meta["publico"]
    try:
        if os.path.isfile(os.path.join(raiz, "wp-config.php")):
            hecho = _wordpress(dict(meta, publico=raiz), raiz, bd, usuario, clave)
        elif os.path.isfile(os.path.join(raiz, "configuration.php")) and os.path.isdir(os.path.join(raiz, "administrator")):
            hecho = _joomla(meta, raiz, bd, usuario, clave)
        elif any(os.path.isfile(os.path.join(d, ".env")) for d in (raiz, meta["publico"])):
            hecho = _env(meta, raiz, bd, usuario, clave)
        else:
            return {"aplicacion": None, "conexion": "pendiente"}
    except ErrorSitio as e:
        return {"aplicacion": None, "conexion": "pendiente", "aviso": str(e)}
    ejecutar(["chown", "-R", f"{meta['usuario']}:www-data", meta["publico"]])
    return {**hecho, "conexion": "actualizada"}
