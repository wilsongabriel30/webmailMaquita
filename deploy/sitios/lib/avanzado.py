"""Configuración avanzada de un sitio (panel → Sitios web → «Avanzado»), para quien sabe lo que hace.

- Reglas propias de nginx: un archivo por sitio (/etc/maquita-sitios/nginx-extra/<dominio>.conf) que el vhost
  incluye dentro de su server{}. El vhost generado se puede ver pero no editar (el panel lo regenera).
- Ajustes de PHP del sitio: memoria, subidas, tiempos y errores, con límites razonables (no la configuración
  libre del pool: cambiaría el usuario o el encierro del sitio).
- Archivos de configuración de la aplicación (wp-config.php, .env, configuration.php…) o cualquier archivo de texto
  dentro de la carpeta pública.

Antes de cada cambio se guarda automáticamente la versión anterior (las 50 últimas por sitio, restaurables) y se
comprueba la configuración: si nginx o PHP-FPM la rechazan, se vuelve sola a la anterior y se muestra el motivo.
"""

import json
import os
import re
import subprocess
import time

from comun import ErrorSitio, ejecutar, guardar_meta, leer_meta

EXTRA = "/etc/maquita-sitios/nginx-extra"
VERSIONES = "/var/lib/maquita-sitios/versiones"
SUBIDAS = "/var/lib/maquita-sitios/subidas"
RE_TEXTO = re.compile(r"^[0-9a-f]{32}\.txt$")
MAX_ARCHIVO = 1024 * 1024
CONSERVAR = 50
SUGERIDOS = ("wp-config.php", "configuration.php", ".env", "config.php", "config/config.php", "config/database.ini",
             "local.xml", "settings.php", "sites/default/settings.php", ".user.ini", "robots.txt", "llms.txt")
# Directivas que no tienen sentido en las reglas de un sitio o que lo sacarían de su encierro.
PROHIBIDAS = re.compile(r"^\s*(load_module|include|user|worker_\w+|pid|env|lua_\w+|\w+_by_lua\w*|perl\w*|"
                        r"ssl_certificate\w*|access_by_\w+|js_\w+)\b", re.M)
RE_RUTA = re.compile(r"^\s*(root|alias)\s+([^;]+);", re.M)
PHP_AJUSTES = {  # nombre → (tipo, mínimo, máximo)
    "memory_limit": ("M", 64, 2048), "upload_max_filesize": ("M", 2, 1024), "post_max_size": ("M", 2, 1024),
    "max_execution_time": ("s", 30, 900), "max_input_time": ("s", 30, 900), "max_input_vars": ("n", 1000, 50000),
    "display_errors": ("b", 0, 1),
}


def ruta_extra(dominio):
    return os.path.join(EXTRA, f"{dominio}.conf")


# --- Versiones (copia automática antes de cada cambio) ---


def _carpeta_versiones(dominio):
    carpeta = os.path.join(VERSIONES, dominio)
    os.makedirs(carpeta, mode=0o700, exist_ok=True)
    return carpeta


def _indice(dominio):
    try:
        with open(os.path.join(_carpeta_versiones(dominio), "indice.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def respaldar(dominio, tipo, ruta, contenido):
    """Guarda la versión que se va a reemplazar. `ruta` es la del archivo (o «php» para los ajustes)."""
    carpeta = _carpeta_versiones(dominio)
    indice = _indice(dominio)
    vid = time.strftime("%Y%m%d-%H%M%S") + f"-{len(indice) % 1000:03d}"
    with open(os.open(os.path.join(carpeta, vid), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "wb") as f:
        f.write(contenido if isinstance(contenido, bytes) else contenido.encode())
    indice.append({"id": vid, "fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "tipo": tipo, "ruta": ruta,
                   "bytes": len(contenido)})
    for viejo in indice[:-CONSERVAR]:
        try:
            os.remove(os.path.join(carpeta, viejo["id"]))
        except OSError:
            pass
    indice = indice[-CONSERVAR:]
    with open(os.path.join(carpeta, "indice.json"), "w") as f:
        json.dump(indice, f, ensure_ascii=False)
    return vid


def _leer_subida(nombre):
    if not RE_TEXTO.match(nombre or ""):
        raise ErrorSitio("contenido no válido")
    ruta = os.path.join(SUBIDAS, nombre)
    try:
        if os.path.islink(ruta) or os.path.getsize(ruta) > MAX_ARCHIVO:
            raise ErrorSitio("el contenido supera 1 MB")
        with open(ruta, "rb") as f:
            return f.read()
    except FileNotFoundError:
        raise ErrorSitio("no llegó el contenido")
    finally:
        if os.path.lexists(ruta):
            os.remove(ruta)


# --- nginx ---


def _validar_nginx(meta, texto):
    if PROHIBIDAS.search(texto):
        raise ErrorSitio(f"directiva no permitida en las reglas del sitio: «{PROHIBIDAS.search(texto).group(1)}»")
    for _, ruta in RE_RUTA.findall(texto):
        ruta = ruta.strip().strip("'\"")
        if "$" not in ruta and not os.path.realpath(ruta).startswith(meta["base"] + "/"):
            raise ErrorSitio(f"root/alias solo pueden apuntar dentro de la carpeta del sitio ({meta['base']})")


def guardar_nginx(dominio, subida):
    import sitio

    meta = leer_meta(dominio)
    texto = _leer_subida(subida).decode("utf-8", "replace").replace("\r\n", "\n")
    _validar_nginx(meta, texto)
    ruta = ruta_extra(dominio)
    anterior = open(ruta).read() if os.path.exists(ruta) else ""
    respaldar(dominio, "nginx", ruta, anterior)
    os.makedirs(EXTRA, mode=0o755, exist_ok=True)

    def poner(contenido):
        if contenido.strip():
            with open(ruta, "w") as f:
                f.write(contenido.rstrip() + "\n")
        elif os.path.exists(ruta):
            os.remove(ruta)
        sitio.escribir_vhost(meta)

    poner(texto)
    r = subprocess.run(["nginx", "-t"], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        poner(anterior)
        motivo = [l for l in r.stderr.splitlines() if "emerg" in l or "error" in l]
        raise ErrorSitio("nginx rechazó las reglas y se dejaron las anteriores: "
                         + (motivo[0].split("] ", 1)[-1][:300] if motivo else "configuración no válida"))
    ejecutar(["systemctl", "reload", "nginx"])
    return ver(dominio)


# --- PHP ---


def _ajustes_php(datos):
    limpio = {}
    for nombre, valor in (datos or {}).items():
        if nombre not in PHP_AJUSTES or valor in (None, ""):
            continue
        tipo, minimo, maximo = PHP_AJUSTES[nombre]
        try:
            n = int(str(valor).rstrip("Mm"))
        except ValueError:
            raise ErrorSitio(f"valor no válido para {nombre}")
        if not minimo <= n <= maximo:
            raise ErrorSitio(f"{nombre} debe estar entre {minimo} y {maximo}")
        limpio[nombre] = f"{n}M" if tipo == "M" else ("on" if n else "off") if tipo == "b" else str(n)
    return limpio


def guardar_php(dominio, datos):
    import sitio

    meta = leer_meta(dominio)
    nuevos = _ajustes_php(datos)
    anteriores = meta.get("php_ajustes", {})
    respaldar(dominio, "php", "php", json.dumps(anteriores))

    def poner(ajustes):
        meta["php_ajustes"] = ajustes
        guardar_meta(meta)
        sitio.escribir_pool(meta)

    poner(nuevos)
    r = subprocess.run([f"php-fpm{meta['php']}", "-t"], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        poner(anteriores)
        raise ErrorSitio("PHP-FPM rechazó los ajustes y se dejaron los anteriores")
    sitio.recargar_php(meta)
    return ver(dominio)


# --- Archivos de la aplicación ---


def _ruta_archivo(meta, relativa):
    relativa = str(relativa or "").lstrip("/")
    if not relativa or "\x00" in relativa or len(relativa) > 300:
        raise ErrorSitio("ruta no válida")
    ruta = os.path.realpath(os.path.join(meta["publico"], relativa))
    if not ruta.startswith(os.path.realpath(meta["publico"]) + "/") or os.path.islink(os.path.join(meta["publico"], relativa)):
        raise ErrorSitio("solo se editan archivos dentro de la carpeta pública del sitio")
    return ruta


def ver_archivo(dominio, relativa):
    meta = leer_meta(dominio)
    ruta = _ruta_archivo(meta, relativa)
    if not os.path.isfile(ruta):
        return {"ruta": relativa, "existe": False, "contenido": ""}
    if os.path.getsize(ruta) > MAX_ARCHIVO:
        raise ErrorSitio("el archivo supera 1 MB: edítelo por SFTP")
    with open(ruta, "rb") as f:
        datos = f.read()
    if b"\x00" in datos[:8192]:
        raise ErrorSitio("no es un archivo de texto")
    return {"ruta": relativa, "existe": True, "contenido": datos.decode("utf-8", "replace")}


def guardar_archivo(dominio, relativa, subida):
    meta = leer_meta(dominio)
    ruta = _ruta_archivo(meta, relativa)
    contenido = _leer_subida(subida)
    if os.path.isfile(ruta):
        with open(ruta, "rb") as f:
            respaldar(dominio, "archivo", relativa, f.read())
        estado = os.stat(ruta)
        modo, uid, gid = estado.st_mode & 0o7777, estado.st_uid, estado.st_gid
    else:
        import pwd

        respaldar(dominio, "archivo", relativa, b"")
        modo, uid, gid = 0o640, pwd.getpwnam(meta["usuario"]).pw_uid, pwd.getpwnam("www-data").pw_gid
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
    tmp = ruta + ".guardando"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, modo), "wb") as f:
        f.write(contenido)
    os.chown(tmp, uid, gid)
    os.chmod(tmp, modo)
    os.replace(tmp, ruta)
    if ruta.endswith(".php"):
        r = subprocess.run(["php", "-l", ruta], capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return {**ver(dominio), "aviso": "Guardado, pero PHP encuentra un error de sintaxis: "
                    + (r.stdout.strip().splitlines() or ["?"])[0][:300] + ". Puede restaurar la versión anterior."}
    return ver(dominio)


# --- Ver y restaurar ---


def ver(dominio):
    import sitio

    meta = leer_meta(dominio)
    with open(sitio._ruta_vhost(dominio)) as f:
        vhost = f.read()
    extra = open(ruta_extra(dominio)).read() if os.path.exists(ruta_extra(dominio)) else ""
    sugeridos = [s for s in SUGERIDOS if os.path.isfile(os.path.join(meta["publico"], s))]
    return {"dominio": dominio, "vhost": vhost, "nginx_propias": extra, "php": meta.get("php_ajustes", {}),
            "php_limites": {k: [v[1], v[2]] for k, v in PHP_AJUSTES.items()}, "archivos": sugeridos,
            "versiones": list(reversed(_indice(dominio)))}


def restaurar(dominio, vid):
    if not re.fullmatch(r"\d{8}-\d{6}-\d{3}", vid or ""):
        raise ErrorSitio("versión no válida")
    entrada = next((v for v in _indice(dominio) if v["id"] == vid), None)
    if not entrada:
        raise ErrorSitio("esa versión no existe")
    with open(os.path.join(_carpeta_versiones(dominio), vid), "rb") as f:
        contenido = f.read()
    # Se restaura por el mismo camino que un cambio: con su copia previa y su comprobación.
    nombre = os.urandom(16).hex() + ".txt"
    with open(os.open(os.path.join(SUBIDAS, nombre), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as f:
        f.write(contenido)
    if entrada["tipo"] == "nginx":
        return guardar_nginx(dominio, nombre)
    if entrada["tipo"] == "php":
        os.remove(os.path.join(SUBIDAS, nombre))
        return guardar_php(dominio, json.loads(contenido or b"{}"))
    return guardar_archivo(dominio, entrada["ruta"], nombre)
