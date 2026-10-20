"""Versiones de PHP y extensiones («Avanzado» → PHP).

Debian trae una sola versión de PHP (8.4 en Debian 13). Para otras (más nuevas o más antiguas, que piden
algunas aplicaciones) se activa el repositorio de Ondřej Surý, mantenedor de PHP en Debian: paquetes firmados
con su clave (`debsuryorg-archive-keyring`), instalados por apt como cualquier otro. Cada versión instalada
tiene su PHP-FPM; cada sitio usa la que se elija (su pool pasa al PHP-FPM de esa versión y el socket no
cambia, así que el vhost tampoco).

Las extensiones se instalan para una versión entera (paquete php<versión>-<extensión>) y se cargan en todos los
sitios de esa versión; solo se ofrecen las de una lista conocida.
"""

import glob
import os
import re
import subprocess

from comun import ErrorSitio, ejecutar, guardar_meta, leer_meta

REPO_LISTA = "/etc/apt/sources.list.d/php-sury.list"
REPO_CLAVE = "/usr/share/keyrings/deb.sury.org-php.gpg"
RE_VERSION = re.compile(r"^[578]\.[0-9]$")
# Extensiones de la instalación base: también se ponen al instalar otra versión, para que las aplicaciones
# del catálogo funcionen igual con cualquiera.
BASE = ("cli", "fpm", "mysql", "xml", "mbstring", "curl", "zip", "gd", "intl", "bcmath", "imagick", "soap",
        "pgsql", "gmp", "ldap", "apcu", "sqlite3", "opcache", "readline")
EXTENSIONES = {
    "redis": "Redis (caché y sesiones)", "memcached": "Memcached", "igbinary": "igbinary (serialización)",
    "msgpack": "MessagePack", "mongodb": "MongoDB", "yaml": "YAML", "uuid": "UUID", "ssh2": "SSH2/SFTP",
    "tidy": "Tidy (HTML)", "xsl": "XSL", "bz2": "bzip2", "odbc": "ODBC", "snmp": "SNMP", "enchant": "Enchant",
    "gnupg": "GnuPG", "imap": "IMAP", "xmlrpc": "XML-RPC", "sqlsrv": "SQL Server", "oauth": "OAuth",
    "amqp": "AMQP (RabbitMQ)", "zstd": "Zstandard", "lz4": "LZ4", "smbclient": "SMB/CIFS",
    "maxminddb": "MaxMind GeoIP2", "excimer": "Excimer (perfilado)", "decimal": "Decimal",
    "ast": "AST", "ds": "Estructuras de datos (ds)", "grpc": "gRPC", "protobuf": "Protocol Buffers",
    "mailparse": "Mailparse", "raphf": "raphf", "http": "pecl_http", "solr": "Solr", "xdebug": "Xdebug (depuración: solo para pruebas)",
    **{e: e for e in BASE if e not in ("cli", "fpm", "readline")},
}


def _apt(*args, tiempo=1200):
    return ejecutar(["apt-get", "-y", "-q", "-o", "Dpkg::Options::=--force-confold", *args], tiempo=tiempo,
                    env_extra={"DEBIAN_FRONTEND": "noninteractive"})


def instaladas():
    return sorted((os.path.basename(os.path.dirname(os.path.dirname(p))) for p in glob.glob("/etc/php/*/fpm/php-fpm.conf")
                   if os.path.exists(f"/usr/sbin/php-fpm{p.split('/')[3]}")), key=lambda v: tuple(map(int, v.split("."))))


def repositorio_activo():
    return os.path.exists(REPO_LISTA)


def disponibles():
    """Versiones que apt puede instalar (con el repositorio activo, todas las que publica)."""
    r = subprocess.run(["apt-cache", "pkgnames", "php"], capture_output=True, text=True, timeout=120)
    vs = {m.group(1) for m in (re.fullmatch(r"php([578]\.[0-9])-fpm", n) for n in r.stdout.split()) if m}
    return sorted(vs, key=lambda v: tuple(map(int, v.split("."))))


def _paquete_existe(nombre):
    r = subprocess.run(["apt-cache", "show", "--no-all-versions", nombre], capture_output=True, text=True, timeout=120)
    return r.returncode == 0 and "Package:" in r.stdout


def activar_repositorio():
    if repositorio_activo():
        return estado()
    codigo = subprocess.run(["sh", "-c", ". /etc/os-release && echo $VERSION_CODENAME"], capture_output=True,
                            text=True).stdout.strip()
    if not re.fullmatch(r"[a-z]+", codigo):
        raise ErrorSitio("no se reconoce la versión de Debian")
    paquete = "/var/cache/apt/archives/debsuryorg-archive-keyring.deb"
    ejecutar(["curl", "-fsSL", "--proto", "=https", "-o", paquete, "https://packages.sury.org/debsuryorg-archive-keyring.deb"],
             tiempo=120)
    ejecutar(["dpkg", "-i", paquete])
    if not os.path.exists(REPO_CLAVE):
        raise ErrorSitio("la clave del repositorio no quedó instalada")
    with open(REPO_LISTA, "w") as f:
        f.write(f"# Versiones de PHP (panel → Avanzado → PHP)\n"
                f"deb [signed-by={REPO_CLAVE}] https://packages.sury.org/php/ {codigo} main\n")
    try:
        _apt("update", tiempo=600)
    except ErrorSitio:
        os.remove(REPO_LISTA)
        _apt("update", tiempo=600)
        raise ErrorSitio("no se pudo leer el repositorio de versiones de PHP: se dejó como estaba")
    return estado()


def _reserva(version):
    """PHP-FPM no arranca sin ningún pool: uno mínimo, sin sitio, como en la versión de serie."""
    ruta = f"/etc/php/{version}/fpm/pool.d/www.conf"
    if os.path.exists(ruta):
        os.remove(ruta)  # el pool de ejemplo del paquete corre como www-data: no se usa
    with open(f"/etc/php/{version}/fpm/pool.d/reserva.conf", "w") as f:
        f.write(f"; Pool mínimo para que php{version}-fpm arranque sin sitios. No sirve nada.\n[reserva]\n"
                "user = nobody\ngroup = nogroup\n"
                f"listen = /run/php/reserva{version}.sock\nlisten.owner = root\nlisten.group = root\nlisten.mode = 0600\n"
                "pm = ondemand\npm.max_children = 1\n")


def instalar_version(version):
    if not RE_VERSION.match(version or ""):
        raise ErrorSitio("versión de PHP no válida")
    if version in instaladas():
        return estado()
    if version not in disponibles():
        raise ErrorSitio(f"PHP {version} no está disponible" + ("" if repositorio_activo() else
                         ": active antes el repositorio de versiones de PHP"))
    paquetes = [f"php{version}-{e}" for e in BASE if _paquete_existe(f"php{version}-{e}")]
    _apt("install", "--no-install-recommends", *paquetes)
    _reserva(version)
    ejecutar(["systemctl", "enable", "--now", f"php{version}-fpm"])
    ejecutar([f"php-fpm{version}", "-t"])
    ejecutar(["systemctl", "restart", f"php{version}-fpm"])
    return estado()


def extensiones(version):
    """Módulos cargados en esa versión y extensiones de la lista que se pueden instalar."""
    if version not in instaladas():
        raise ErrorSitio(f"PHP {version} no está instalado")
    r = subprocess.run([f"/usr/bin/php{version}", "-m"], capture_output=True, text=True, timeout=60)
    cargadas = sorted({l.strip().lower() for l in r.stdout.splitlines() if l.strip() and not l.startswith("[")})
    r = subprocess.run(["dpkg-query", "-W", "-f", "${Package} ${Status}\n", f"php{version}-*"], capture_output=True,
                       text=True, timeout=60)
    puestas = {l.split()[0].split("-", 1)[1] for l in r.stdout.splitlines() if "install ok installed" in l}
    r = subprocess.run(["apt-cache", "pkgnames", f"php{version}-"], capture_output=True, text=True, timeout=120)
    hay = {n.split("-", 1)[1] for n in r.stdout.split()}
    return {"version": version, "cargadas": cargadas,
            "ofrecidas": [{"id": e, "nombre": n, "instalada": e in puestas} for e, n in sorted(EXTENSIONES.items())
                          if e in hay or e in puestas]}


def instalar_extension(version, extension):
    if version not in instaladas():
        raise ErrorSitio(f"PHP {version} no está instalado")
    if extension not in EXTENSIONES:
        raise ErrorSitio("esa extensión no está en la lista")
    if not _paquete_existe(f"php{version}-{extension}"):
        raise ErrorSitio(f"no hay paquete de {extension} para PHP {version}")
    _apt("install", "--no-install-recommends", f"php{version}-{extension}")
    ejecutar([f"php-fpm{version}", "-t"])
    ejecutar(["systemctl", "reload", f"php{version}-fpm"])
    return extensiones(version)


def quitar_extension(version, extension):
    if extension in BASE:
        raise ErrorSitio("las extensiones de la instalación base no se quitan: las usan las aplicaciones del catálogo")
    if extension not in EXTENSIONES or version not in instaladas():
        raise ErrorSitio("extensión o versión no válida")
    _apt("remove", f"php{version}-{extension}")
    ejecutar(["systemctl", "reload", f"php{version}-fpm"])
    return extensiones(version)


def cambiar_version(dominio, version):
    """El sitio pasa a otra versión de PHP; si PHP-FPM la rechaza, vuelve a la anterior."""
    import sitio

    meta = leer_meta(dominio)
    if meta.get("app") == "propia":
        raise ErrorSitio("las aplicaciones propias no usan PHP")
    if version not in instaladas():
        raise ErrorSitio(f"PHP {version} no está instalado")
    anterior = meta["php"]
    if version == anterior:
        return estado(dominio)
    ruta_vieja = sitio._ruta_pool(meta)
    meta["php"] = version
    sitio.escribir_pool(meta)
    r = subprocess.run([f"php-fpm{version}", "-t"], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        os.remove(sitio._ruta_pool(meta))
        meta["php"] = anterior
        raise ErrorSitio(f"PHP-FPM {version} rechazó la configuración del sitio: se deja en {anterior}")
    if os.path.exists(ruta_vieja):
        os.remove(ruta_vieja)
    guardar_meta(meta)
    ejecutar(["systemctl", "reload", f"php{version}-fpm"])
    ejecutar(["systemctl", "reload", f"php{anterior}-fpm"])
    return estado(dominio)


def en_uso():
    from comun import todos_los_meta

    uso = {}
    for m in todos_los_meta():
        if m.get("app") != "propia" and m.get("php"):
            uso[m["php"]] = uso.get(m["php"], 0) + 1
    return uso


def estado(dominio=None):
    datos = {"instaladas": instaladas(), "disponibles": disponibles(), "repositorio": repositorio_activo(),
             "en_uso": en_uso()}
    if dominio:
        datos["sitio"] = leer_meta(dominio).get("php")
    return datos
