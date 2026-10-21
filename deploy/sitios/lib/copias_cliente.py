"""Copias del sitio que controla su dueño: crear ahora, listar, descargar, restaurar y borrar.

Son aparte de los respaldos del servidor (deploy/respaldos, restic), que hace y restaura el administrador
general: estas viven en COPIAS/<dominio>/ (fuera de /srv/sitios, así que restic no las duplica) y cada una es un
solo .tar.gz que se puede bajar y abrir en cualquier equipo:

    publico/        la carpeta pública del sitio
    app/            el código de la aplicación propia, si la tiene
    bases/<n>.sql   un volcado SQL por base (la principal MariaDB y las adicionales MariaDB o PostgreSQL)
    copia.json      dominio, fecha, motivo y bases

Como mucho TOPE copias por sitio. Restaurar exige sitio para una copia previa automática (la del estado de
ese momento), que se hace siempre antes de tocar nada. Al dar de baja el sitio, sus copias van a la papelera
con él.
"""

import fcntl
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time

from comun import ErrorSitio, ejecutar, leer_meta, volcar

COPIAS = "/var/lib/maquita-sitios/copias"
TOPE = 5
RE_ID = re.compile(r"^\d{8}-\d{6}$")
MARGEN = 200 * 1048576  # espacio libre que debe quedar tras la copia


def _carpeta(dominio):
    return os.path.join(COPIAS, dominio)


def _archivo(dominio, ident):
    if not RE_ID.match(ident or ""):
        raise ErrorSitio("copia no válida")
    return os.path.join(_carpeta(dominio), f"{ident}.tar.gz")


def _bases(meta):
    return ([("mariadb", meta["bd"])] if meta.get("bd") else []) + \
        [(b["motor"], b["nombre"]) for b in meta.get("bases", [])]


def _partes(meta):
    """Carpetas del sitio que entran en la copia: (nombre en la copia, ruta)."""
    salida = [("publico", meta["publico"])]
    if meta.get("app_dir") and os.path.isdir(meta["app_dir"]):
        salida.append(("app", meta["app_dir"]))
    return salida


class _Cerrojo:
    """Una sola copia o restauración a la vez por sitio."""

    def __init__(self, dominio):
        os.makedirs(_carpeta(dominio), mode=0o700, exist_ok=True)
        self.ruta = os.path.join(_carpeta(dominio), ".cerrojo")

    def __enter__(self):
        self.f = open(self.ruta, "w")
        try:
            fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.f.close()
            raise ErrorSitio("ya hay una copia o una restauración de este sitio en curso")
        return self

    def __exit__(self, *_):
        self.f.close()


def _indice(dominio):
    carpeta = _carpeta(dominio)
    if not os.path.isdir(carpeta):
        return []
    salida = []
    for n in sorted(os.listdir(carpeta), reverse=True):
        if not (n.endswith(".tar.gz") and RE_ID.match(n[:-7])):
            continue
        ident = n[:-7]
        try:
            with open(os.path.join(carpeta, f"{ident}.json")) as f:
                datos = json.load(f)
        except (OSError, ValueError):
            datos = {}
        salida.append({"id": ident, "fecha": datos.get("fecha") or ident, "motivo": datos.get("motivo", "manual"),
                       "bases": datos.get("bases", []), "bytes": os.path.getsize(os.path.join(carpeta, n))})
    return salida


def listar(dominio):
    leer_meta(dominio)
    return {"dominio": dominio, "copias": _indice(dominio), "tope": TOPE}


def _tamano(ruta):
    total = 0
    for actual, _dirs, archivos in os.walk(ruta):
        for a in archivos:
            try:
                total += os.lstat(os.path.join(actual, a)).st_size
            except OSError:
                pass
    return total


def _volcar(motor, nombre, destino):
    if motor == "mariadb":
        volcar(["mariadb-dump", "--protocol=socket", "-u", "root", "--single-transaction", "--hex-blob",
                "--routines", "--triggers", nombre], destino)
    else:
        volcar(["runuser", "-u", "postgres", "--", "pg_dump", nombre], destino)


def _crear(meta, motivo):
    dominio = meta["dominio"]
    carpeta = _carpeta(dominio)
    if len(_indice(dominio)) >= TOPE:
        raise ErrorSitio(f"el sitio ya tiene {TOPE} copias (el máximo): borre alguna antes de crear otra")
    necesario = sum(_tamano(r) for _, r in _partes(meta)) + MARGEN
    if shutil.disk_usage(carpeta).free < necesario:
        raise ErrorSitio("no hay espacio libre suficiente en el servidor para la copia")
    ident = time.strftime("%Y%m%d-%H%M%S")
    while os.path.exists(os.path.join(carpeta, f"{ident}.tar.gz")):
        time.sleep(1)
        ident = time.strftime("%Y%m%d-%H%M%S")
    final = os.path.join(carpeta, f"{ident}.tar.gz")
    parcial = final + ".parcial"
    bases = _bases(meta)
    manifiesto = {"dominio": dominio, "fecha": time.strftime("%Y-%m-%d %H:%M"), "motivo": motivo,
                  "bases": [{"motor": m, "nombre": n} for m, n in bases]}
    try:
        with tempfile.TemporaryDirectory(dir=carpeta) as tmp, \
                open(os.open(parcial, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "wb") as salida, \
                tarfile.open(fileobj=salida, mode="w:gz", compresslevel=6) as tar:
            for nombre, ruta in _partes(meta):
                tar.add(ruta, arcname=nombre)  # los enlaces simbólicos se guardan como enlaces, no se siguen
            for motor, nombre in bases:
                volcado = os.path.join(tmp, f"{nombre}.sql")
                _volcar(motor, nombre, volcado)
                tar.add(volcado, arcname=f"bases/{nombre}.sql")
            ruta_manifiesto = os.path.join(tmp, "copia.json")
            with open(ruta_manifiesto, "w") as f:
                json.dump(manifiesto, f, ensure_ascii=False, indent=2)
            tar.add(ruta_manifiesto, arcname="copia.json")
        os.replace(parcial, final)
    finally:
        if os.path.exists(parcial):
            os.remove(parcial)
    with open(os.open(os.path.join(carpeta, f"{ident}.json"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
        json.dump(manifiesto, f, ensure_ascii=False)
    return {"id": ident, "bytes": os.path.getsize(final), **manifiesto}


def crear(dominio, motivo="manual"):
    meta = leer_meta(dominio)
    with _Cerrojo(dominio):
        return {"dominio": dominio, "copia": _crear(meta, motivo)}


def descargar(dominio, ident, subidas):
    """Deja la copia en subidas/ para que el panel la entregue y la borre."""
    leer_meta(dominio)
    origen = _archivo(dominio, ident)
    if not os.path.isfile(origen):
        raise ErrorSitio("esa copia no existe")
    nombre = os.urandom(16).hex() + ".descarga"
    destino = os.path.join(subidas, nombre)
    shutil.copyfile(origen, destino)
    os.chmod(destino, 0o640)  # el grupo del panel lo da la carpeta subidas/ (setgid)
    return {"dominio": dominio, "archivo": nombre, "nombre": f"{dominio}-{ident}.tar.gz",
            "bytes": os.path.getsize(destino)}


def borrar(dominio, ident):
    leer_meta(dominio)
    archivo = _archivo(dominio, ident)
    if not os.path.isfile(archivo):
        raise ErrorSitio("esa copia no existe")
    with _Cerrojo(dominio):
        os.remove(archivo)
        if os.path.exists(archivo[:-7] + ".json"):
            os.remove(archivo[:-7] + ".json")
    return {"dominio": dominio, "borrada": ident}


def _permisos(meta, nombre, ruta, dueno):
    """Tras restaurar: del usuario del sitio, como antes (nunca de root)."""
    if nombre == "publico":
        from apps.receta import permisos

        permisos(meta)
    else:
        ejecutar(["chown", "-R", f"{dueno[0]}:{dueno[1]}", ruta])


def _restaurar_base(motor, nombre, archivo):
    with open(archivo, "rb") as entrada:
        if motor == "mariadb":
            ejecutar(["mariadb", "--protocol=socket", "-u", "root", "-e",
                      f"DROP DATABASE IF EXISTS `{nombre}`; CREATE DATABASE `{nombre}` "
                      "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"])
            orden = ["mariadb", "--protocol=socket", "-u", "root", nombre]
        else:
            ejecutar(["runuser", "-u", "postgres", "--", "dropdb", "--if-exists", "--force", nombre])
            ejecutar(["runuser", "-u", "postgres", "--", "createdb", "-O", nombre, nombre])
            orden = ["runuser", "-u", "postgres", "--", "psql", "-v", "ON_ERROR_STOP=1", "-q", "-d", nombre]
        r = subprocess.run(orden, stdin=entrada, capture_output=True, timeout=3600, cwd="/tmp")
    if r.returncode != 0:
        detalle = r.stderr.decode(errors="replace").strip().splitlines()
        raise ErrorSitio(f"no se pudo restaurar la base {nombre}" + (f": {detalle[-1][:200]}" if detalle else ""))


def restaurar(dominio, ident):
    meta = leer_meta(dominio)
    archivo = _archivo(dominio, ident)
    if not os.path.isfile(archivo):
        raise ErrorSitio("esa copia no existe")
    if len(_indice(dominio)) >= TOPE:
        raise ErrorSitio(f"para restaurar hace falta sitio para la copia previa automática: borre una de las {TOPE} copias")
    with _Cerrojo(dominio):
        previa = _crear(meta, f"antes de restaurar {ident}")
        conocidas = {n: m for m, n in _bases(meta)}
        # Se extrae en la carpeta del sitio (de root, 755): mismo sistema de archivos, así el cambio es un rename.
        with tempfile.TemporaryDirectory(dir=meta["base"], prefix=".restaurando-") as tmp:
            omitidos = []
            with tarfile.open(archivo, "r:gz") as tar:
                tar.extractall(tmp, filter=lambda m, destino: _filtro(m, destino, omitidos))
            # Todo se comprueba antes de tocar el sitio.
            volcados = []
            if os.path.isdir(os.path.join(tmp, "bases")):
                for n in sorted(os.listdir(os.path.join(tmp, "bases"))):
                    if n.endswith(".sql") and n[:-4] in conocidas:
                        volcados.append((conocidas[n[:-4]], n[:-4], os.path.join(tmp, "bases", n)))
            if not os.path.isdir(os.path.join(tmp, "publico")):
                raise ErrorSitio("la copia no tiene la carpeta pública del sitio")
            restauradas = []
            for nombre, ruta in _partes(meta):
                origen = os.path.join(tmp, nombre)
                if not os.path.isdir(origen):
                    continue
                info = os.stat(ruta)
                vieja = f"{ruta}.antes-{ident}"
                os.rename(ruta, vieja)
                os.rename(origen, ruta)
                os.chmod(ruta, info.st_mode & 0o7777)
                os.chown(ruta, info.st_uid, info.st_gid)
                shutil.rmtree(vieja, ignore_errors=True)
                _permisos(meta, nombre, ruta, (info.st_uid, info.st_gid))
                restauradas.append(nombre)
            for motor, nombre, volcado in volcados:
                _restaurar_base(motor, nombre, volcado)
    if meta.get("app") == "propia" and (meta.get("propia") or {}).get("tipo") != "estatico":
        subprocess.run(["systemctl", "try-restart", f"sitio-{meta['usuario']}"], capture_output=True, timeout=120)
    return {"dominio": dominio, "restaurada": ident, "carpetas": restauradas,
            "bases": [n for _, n, _ in volcados], "copia_previa": previa["id"], "enlaces_omitidos": omitidos[:50]}


def _filtro(miembro, destino, omitidos):
    """filter="data" (sin rutas absolutas ni «..», sin dispositivos ni setuid), pero un enlace simbólico que apunta
    fuera del sitio se omite en vez de cancelar toda la restauración (se anota para avisar)."""
    try:
        return tarfile.data_filter(miembro, destino)
    except (tarfile.AbsoluteLinkError, tarfile.LinkOutsideDestinationError):
        omitidos.append(miembro.name)
        return None


def quitar(dominio, papelera=None):
    """Baja del sitio: las copias van a `papelera` (la carpeta del sitio en la papelera) o se borran."""
    carpeta = _carpeta(dominio)
    if not os.path.isdir(carpeta):
        return
    if papelera and os.path.isdir(papelera):
        shutil.move(carpeta, os.path.join(papelera, "copias-del-sitio"))
    else:
        shutil.rmtree(carpeta, ignore_errors=True)
