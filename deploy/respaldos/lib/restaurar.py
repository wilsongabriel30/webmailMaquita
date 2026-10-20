"""Restaurar desde un respaldo, sin riesgo para lo que hay:

- Un sitio web: antes se respalda su estado actual (etiqueta «antes-de-restaurar», no caduca); luego se
  devuelven sus archivos y sus bases de datos (la principal y las adicionales) tal como estaban.
- Un buzón: sus correos del respaldo se copian a una carpeta nueva «Restaurado-AAAAMMDD-HHMM» dentro del mismo
  buzón (con sus subcarpetas). No se borra ni se cambia nada de lo actual.
- Comprobar: integridad del repositorio (una muestra de los datos) y prueba de restauración de la base del
  correo en una base desechable.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile

from ajustes import BASE, CERROJO, REPO_LOCAL, VOLCADOS, ErrorRespaldo, restic

RE_ID = re.compile(r"^[0-9a-f]{8,64}$")
RE_CORREO = re.compile(r"^([a-z0-9][a-z0-9._+-]{0,63})@(([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63})$")


def _id(valor):
    if not RE_ID.match(valor or ""):
        raise ErrorRespaldo("instantánea no válida")
    return valor


def _cmd(orden, entrada=None, tiempo=3600):
    r = subprocess.run(orden, input=entrada, capture_output=True, timeout=tiempo, cwd="/tmp")
    if r.returncode != 0:
        detalle = (r.stderr or r.stdout).decode(errors="replace").strip().splitlines()
        raise ErrorRespaldo(f"{os.path.basename(orden[0])}: " + (detalle[-1][:300] if detalle else f"código {r.returncode}"))
    return r.stdout.decode(errors="replace")


class _Cerrojo:
    def __enter__(self):
        try:
            self.fd = os.open(CERROJO, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise ErrorRespaldo("ya hay un respaldo o una restauración en curso")
        return self

    def __exit__(self, *_):
        os.close(self.fd)
        os.remove(CERROJO)


def _extraer(instantanea, rutas, dentro_de=BASE):
    """Restaura solo esas rutas de la instantánea en una carpeta temporal (por defecto junto a los respaldos,
    solo root; los buzones, bajo /var/vmail para que Dovecot pueda leerlos)."""
    os.makedirs(dentro_de, mode=0o700, exist_ok=True)
    destino = tempfile.mkdtemp(prefix=".restaurar-", dir=dentro_de)
    args = ["restore", instantanea, "--target", destino]
    for ruta in rutas:
        args += ["--include", ruta]
    try:
        restic(REPO_LOCAL, *args)
    except ErrorRespaldo:
        shutil.rmtree(destino, ignore_errors=True)
        raise
    return destino


# --- Sitio web ---


def sitio(dominio, instantanea):
    from respaldo import respaldar

    _id(instantanea)
    ruta_meta = f"/etc/maquita-sitios/{dominio}.json"
    if not re.match(r"^[a-z0-9.-]{4,200}$", dominio) or not os.path.isfile(ruta_meta):
        raise ErrorRespaldo("el sitio no existe en este servidor (se restaura sobre un sitio dado de alta)")
    with open(ruta_meta) as f:
        meta = json.load(f)
    base = meta["base"]
    bases = ([("mariadb", meta["bd"])] if meta.get("bd") else []) + [(b["motor"], b["nombre"]) for b in meta.get("bases", [])]
    volcados = [os.path.join(VOLCADOS, m, f"{n}.{'sql' if m == 'mariadb' else 'dump'}") for m, n in bases]
    # 1) Estado actual a salvo (el sitio y todas las bases), por si hay que deshacer la restauración.
    previo = respaldar(motivo=f"antes de restaurar {dominio}", rutas=[base, VOLCADOS], etiqueta="antes-de-restaurar")
    with _Cerrojo():
        tmp = _extraer(instantanea, [base] + volcados)
        try:
            origen = tmp + base
            if not os.path.isdir(origen):
                raise ErrorRespaldo(f"esa instantánea no tiene el sitio {dominio}")
            # Todo se lee ANTES de tocar nada: si falta o no se puede leer un volcado, el sitio queda como estaba.
            contenidos = []
            for archivo in volcados:
                if not os.path.isfile(tmp + archivo):
                    raise ErrorRespaldo(f"esa instantánea no tiene la base {os.path.basename(archivo)}")
                with open(tmp + archivo, "rb") as f:
                    contenidos.append(f.read())
            # 2) Archivos: idénticos a los del respaldo (lo añadido después se quita; está en el respaldo previo).
            _cmd(["rsync", "-a", "--delete", origen + "/", base + "/"])
            # 3) Bases de datos.
            for (motor, nombre), contenido in zip(bases, contenidos):
                if motor == "mariadb":
                    _cmd(["mariadb", "--protocol=socket", "-u", "root", "-e", f"DROP DATABASE IF EXISTS `{nombre}`"])
                    _cmd(["mariadb", "--protocol=socket", "-u", "root"], entrada=contenido)
                else:
                    # pg_restore corre como postgres: el volcado le llega por la entrada (no lee la carpeta de root).
                    _cmd(["runuser", "-u", "postgres", "--", "dropdb", "--if-exists", "--force", nombre])
                    _cmd(["runuser", "-u", "postgres", "--", "createdb", "-O", nombre, nombre])
                    _cmd(["runuser", "-u", "postgres", "--", "pg_restore", "--no-owner", "--role", nombre, "-d", nombre],
                         entrada=contenido)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    # 4) Aplicación propia en marcha: que tome los archivos devueltos.
    if meta.get("app") == "propia" and (meta.get("propia") or {}).get("tipo") != "estatico":
        subprocess.run(["systemctl", "try-restart", f"sitio-{meta['usuario']}"], capture_output=True, timeout=120)
    return {"dominio": dominio, "restaurado_desde": instantanea, "bases": [n for _, n in bases],
            "respaldo_previo": previo.get("instantanea")}


# --- Buzón ---


def buzon(correo, instantanea):
    import time

    _id(instantanea)
    m = RE_CORREO.match((correo or "").lower())
    if not m:
        raise ErrorRespaldo("correo no válido")
    usuario, dominio = m.group(1), m.group(2)
    maildir = f"/var/vmail/{dominio}/{usuario}/Maildir"
    if not os.path.isdir(maildir):
        raise ErrorRespaldo("ese buzón no existe en este servidor")
    carpeta = "Restaurado-" + time.strftime("%Y%m%d-%H%M")
    with _Cerrojo():
        tmp = _extraer(instantanea, [maildir], dentro_de="/var/vmail")
        try:
            origen = tmp + maildir
            if not os.path.isdir(origen):
                raise ErrorRespaldo("esa instantánea no tiene ese buzón")
            _cmd(["chown", "-R", "vmail:vmail", tmp])
            os.chmod(tmp, 0o755)
            # doveadm copia los mensajes del respaldo a «carpeta/…» del buzón (sus propias carpetas, sin pisar nada).
            _cmd(["doveadm", "import", "-u", correo, "-s", f"maildir:{origen}", carpeta, "all"], tiempo=7200)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    lista = _cmd(["doveadm", "mailbox", "list", "-u", correo, f"{carpeta}*"]).split()
    total = 0
    for nombre in lista:
        subprocess.run(["doveadm", "mailbox", "subscribe", "-u", correo, nombre], capture_output=True, timeout=60)
        # «Restaurado-…» en sí solo agrupa las subcarpetas (INBOX, Sent…): no es un buzón y no tiene estado.
        r = subprocess.run(["doveadm", "mailbox", "status", "-u", correo, "messages", nombre], capture_output=True,
                           text=True, timeout=60)
        n = re.search(r"messages=(\d+)", r.stdout)
        total += int(n.group(1)) if n else 0
    if not total:
        raise ErrorRespaldo(f"no se encontraron correos de {correo} en esa instantánea")
    return {"buzon": correo, "carpeta": carpeta, "carpetas": [c for c in lista if c != carpeta], "mensajes": total, "restaurado_desde": instantanea}


# --- Comprobar ---


def comprobar():
    """Integridad del repositorio (lee un 5 % de los datos al azar) y restauración de prueba de maildb."""
    with _Cerrojo():
        restic(REPO_LOCAL, "check", "--read-data-subset", "5%", tiempo=4 * 3600)
        ultima = (restic(REPO_LOCAL, "snapshots", "--host", "servidor", "--latest", "1", json_salida=True) or [None])[-1]
        if not ultima:
            raise ErrorRespaldo("todavía no hay respaldos")
        archivo = os.path.join(VOLCADOS, "postgresql", "maildb.dump")
        tmp = _extraer(ultima["short_id"], [archivo])
        prueba = "prueba_restauracion_respaldo"
        try:
            _cmd(["runuser", "-u", "postgres", "--", "dropdb", "--if-exists", prueba])
            _cmd(["runuser", "-u", "postgres", "--", "createdb", prueba])
            with open(tmp + archivo, "rb") as f:
                subprocess.run(["runuser", "-u", "postgres", "--", "pg_restore", "--no-owner", "-d", prueba],
                               stdin=f, capture_output=True, timeout=3600, cwd="/tmp")
            buzones = _cmd(["runuser", "-u", "postgres", "--", "psql", "-tAc", "SELECT count(*) FROM mailbox", prueba]).strip()
        finally:
            subprocess.run(["runuser", "-u", "postgres", "--", "dropdb", "--if-exists", prueba], capture_output=True, cwd="/tmp")
            shutil.rmtree(tmp, ignore_errors=True)
    return {"repositorio": "íntegro", "instantanea": ultima["short_id"], "fecha": ultima["time"][:16].replace("T", " "),
            "prueba_base_correo": f"se restaura ({buzones} buzones)"}
