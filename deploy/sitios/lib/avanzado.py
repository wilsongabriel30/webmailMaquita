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
import shutil
import subprocess
import time

import archivo_seguro
from comun import ErrorSitio, guardar_meta, leer_meta

EXTRA = "/etc/maquita-sitios/nginx-extra"
VERSIONES = "/var/lib/maquita-sitios/versiones"
SUBIDAS = "/var/lib/maquita-sitios/subidas"
RE_TEXTO = re.compile(r"^[0-9a-f]{32}\.txt$")
MAX_ARCHIVO = 1024 * 1024
CONSERVAR = 50
SUGERIDOS = ("wp-config.php", "configuration.php", ".env", "config.php", "config/config.php", "config/database.ini",
             "local.xml", "settings.php", "sites/default/settings.php", ".user.ini", "robots.txt", "llms.txt")
# Directivas que no tienen sentido en las reglas de un sitio o que lo sacarían de su encierro.
PROHIBIDAS = re.compile(r"load_module|include|user|worker_\w+|pid|env|lua_\w+|\w+_by_lua\w*|perl\w*|"
                        r"ssl_certificate\w*|access_by_\w+|js_\w+")
PHP_AJUSTES = {  # nombre → (tipo, mínimo, máximo); «b» sí/no, «z» zona horaria, «o» lista de opciones
    "memory_limit": ("M", 64, 2048), "upload_max_filesize": ("M", 2, 1024), "post_max_size": ("M", 2, 1024),
    "max_execution_time": ("s", 30, 900), "max_input_time": ("s", 30, 900), "max_input_vars": ("n", 1000, 50000),
    "max_file_uploads": ("n", 1, 200), "session.gc_maxlifetime": ("n", 300, 604800),
    "default_socket_timeout": ("n", 10, 600), "output_buffering": ("n", 0, 65536),
    "opcache.revalidate_freq": ("n", 0, 3600),
    "display_errors": ("b", 0, 1), "allow_url_fopen": ("b", 0, 1), "short_open_tag": ("b", 0, 1),
    "opcache.enable": ("b", 0, 1), "permitir_ejecucion": ("b", 0, 1),
    "date.timezone": ("z", None, None), "error_reporting": ("o", None, None),
}
# error_reporting en el pool tiene que ser numérico (las constantes E_* no se evalúan ahí).
NIVELES_ERRORES = {"todos": "32767", "produccion": "22527", "solo_errores": "4437"}


def quitar(dominio):
    """Al dar de baja el sitio: sus reglas propias y sus versiones guardadas."""
    if os.path.exists(ruta_extra(dominio)):
        os.remove(ruta_extra(dominio))
    shutil.rmtree(os.path.join(VERSIONES, dominio), ignore_errors=True)


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


def _sentencias(texto):
    """Cada directiva con sus argumentos. Se corta por «{», «}», «;» y saltos de línea, como empieza nginx una
    directiva: así no se escapa una escrita a mitad de línea (`location /x { root /etc; }`). Si un texto entre
    comillas lleva «;» o «#», se valida de más, nunca de menos."""
    for trozo in re.split(r"[{};\n]", texto):
        palabras = trozo.split(None, 1)
        if not palabras or palabras[0].startswith("#"):
            continue
        yield palabras[0].strip("'\"").replace("\\", "").lower(), (palabras[1] if len(palabras) > 1 else "").strip()


def _validar_nginx(meta, texto):
    import sitio

    for directiva, argumentos in _sentencias(texto):
        if PROHIBIDAS.fullmatch(directiva):
            raise ErrorSitio(f"directiva no permitida en las reglas del sitio: «{directiva}»")
        if directiva.endswith("_pass") and "unix:" in argumentos and argumentos.strip("'\"") != "unix:" + sitio._socket(meta):
            # El socket de PHP de otro sitio ejecutaría código con el usuario de ese sitio.
            raise ErrorSitio("solo se puede pasar al socket de PHP de este sitio")
        if directiva in ("root", "alias"):
            ruta = argumentos.strip("'\"")
            dentro = ruta.startswith(meta["base"] + "/") or ruta.startswith("$document_root")
            if ".." in ruta or not dentro or ("$" not in ruta and not os.path.realpath(ruta).startswith(meta["base"] + "/")):
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
    sitio.recargar_nginx()
    return ver(dominio)


# --- PHP ---


def _ajustes_php(datos):
    limpio = {}
    for nombre, valor in (datos or {}).items():
        if nombre not in PHP_AJUSTES or valor in (None, ""):
            continue
        tipo, minimo, maximo = PHP_AJUSTES[nombre]
        valor = str(valor).strip()
        if tipo == "z":
            if not re.fullmatch(r"[A-Za-z]+(?:/[A-Za-z0-9_+-]+){0,2}|UTC", valor) or not os.path.isfile(f"/usr/share/zoneinfo/{valor}"):
                raise ErrorSitio("zona horaria no válida (p. ej. America/Guayaquil)")
            limpio[nombre] = valor
            continue
        if tipo == "o":
            if valor not in NIVELES_ERRORES:
                raise ErrorSitio("nivel de errores no válido")
            limpio[nombre] = valor
            continue
        try:
            n = int(valor.rstrip("Mm"))
        except ValueError:
            raise ErrorSitio(f"valor no válido para {nombre}")
        if not minimo <= n <= maximo:
            raise ErrorSitio(f"{nombre} debe estar entre {minimo} y {maximo}")
        limpio[nombre] = f"{n}M" if tipo == "M" else ("on" if n else "off") if tipo == "b" else str(n)
    return limpio


def lineas_pool(ajustes):
    """Líneas del pool de PHP-FPM para los ajustes ya validados (las usa plantillas.pool)."""
    lineas = {}
    for nombre, valor in (ajustes or {}).items():
        tipo = PHP_AJUSTES.get(nombre, ("",))[0]
        if nombre == "permitir_ejecucion":
            # Con «sí», PHP puede lanzar programas del sistema (algunas aplicaciones lo piden para miniaturas o
            # tareas); siguen corriendo con el usuario del sitio, pero ya sin el límite de open_basedir.
            if valor == "on":
                lineas["disable_functions"] = "php_admin_value[disable_functions] = pcntl_exec"
        elif nombre == "error_reporting":
            lineas[nombre] = f"php_admin_value[error_reporting] = {NIVELES_ERRORES.get(valor, '22527')}"
        elif tipo == "b":
            lineas[nombre] = f"php_admin_flag[{nombre}] = {valor}"
        else:
            lineas[nombre] = f"php_admin_value[{nombre}] = {valor}"
    return lineas


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


def _relativa(relativa):
    relativa = str(relativa or "").lstrip("/")
    if not relativa or "\x00" in relativa or len(relativa) > 300:
        raise ErrorSitio("ruta no válida")
    return relativa


# Las rutas se abren componente a componente sin seguir enlaces (archivo_seguro): el usuario del
# sitio puede cambiar sus archivos por enlaces simbólicos mientras root los lee o los guarda.
def ver_archivo(dominio, relativa):
    meta = leer_meta(dominio)
    relativa = _relativa(relativa)
    existe, datos, _ = archivo_seguro.leer(meta["publico"], relativa, MAX_ARCHIVO)
    if not existe:
        return {"ruta": relativa, "existe": False, "contenido": ""}
    if datos is None:
        raise ErrorSitio("el archivo supera 1 MB: edítelo por SFTP")
    if b"\x00" in datos[:8192]:
        raise ErrorSitio("no es un archivo de texto")
    return {"ruta": relativa, "existe": True, "contenido": datos.decode("utf-8", "replace")}


def guardar_archivo(dominio, relativa, subida):
    import pwd

    meta = leer_meta(dominio)
    relativa = _relativa(relativa)
    contenido = _leer_subida(subida)
    usuario = pwd.getpwnam(meta["usuario"]).pw_uid
    grupo_web = pwd.getpwnam("www-data").pw_gid
    existe, previo, st = archivo_seguro.leer(meta["publico"], relativa, 64 * 1024 * 1024)
    if existe and previo is not None:
        respaldar(dominio, "archivo", relativa, previo)
        modo, uid, gid = st.st_mode & 0o777, st.st_uid, st.st_gid
    elif existe:
        raise ErrorSitio("el archivo es demasiado grande: edítelo por SFTP")
    else:
        respaldar(dominio, "archivo", relativa, b"")
        modo, uid, gid = 0o640, usuario, grupo_web
    archivo_seguro.escribir(meta["publico"], relativa, contenido, uid, gid, modo,
                            carpetas_como=(usuario, grupo_web, 0o750))
    ruta = os.path.join(meta["publico"], relativa)
    if ruta.endswith(".php"):
        # Se revisa lo guardado por la entrada estándar, no releyendo la ruta (podría ser ya un enlace).
        r = subprocess.run(["php", "-l"], input=contenido.decode("utf-8", "replace"), capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return {**ver(dominio), "aviso": "Guardado, pero PHP encuentra un error de sintaxis: "
                    + (([x for x in (r.stdout + r.stderr).splitlines() if "error" in x.lower() and "Errors parsing" not in x]
                       or ["?"])[0].replace("PHP Parse error:", "").replace("Standard input code", "el archivo").strip()[:300]) + ". Puede restaurar la versión anterior."}
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
            "php_limites": {k: [v[1], v[2]] for k, v in PHP_AJUSTES.items() if v[0] not in ("z", "o")},
            "php_tipos": {k: v[0] for k, v in PHP_AJUSTES.items()}, "php_version": meta.get("php"),
            "archivos": sugeridos,
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
