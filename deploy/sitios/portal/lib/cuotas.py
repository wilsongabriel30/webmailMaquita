"""Cuotas de sitios por dominio asignado (pd_cuotas_sitio, las fija el superadministrador) y su uso.

Sin fila para un dominio valen las de por defecto. El uso se mide en el momento:
- sitios: los que cuelgan del dominio (el propio y sus subdominios);
- disco: lo que ocupan sus carpetas en /srv/sitios (como `du`, sin seguir enlaces);
- bases: el tamaño en MariaDB (information_schema) y PostgreSQL de las bases de esos sitios.
Solo se miran al crear o hacer crecer algo: lo que ya hay no se toca.
"""

import json
import os
import re
import subprocess

import alcance
import rutas
import sesion
from errores import ErrorPortal

POR_DEFECTO = {"max_sitios": 1, "disco_mb": 2048, "bases_mb": 1024}
RE_BASE = re.compile(r"^[a-z0-9_]{1,64}$")
MB = 1024 * 1024


def de(dominio, guardadas=None):
    guardadas = sesion.cuotas_guardadas([dominio]) if guardadas is None else guardadas
    fila = guardadas.get(dominio) or {}
    return {k: int(fila.get(k, v)) for k, v in POR_DEFECTO.items()}


def _bytes_carpeta(ruta):
    total = 0
    for raiz, _dirs, archivos in os.walk(ruta):
        for a in archivos:
            try:
                total += os.lstat(os.path.join(raiz, a)).st_blocks * 512
            except OSError:
                pass
    return total


def disco_mb(sitios):
    return round(sum(_bytes_carpeta(os.path.join(rutas.RAIZ_SITIOS, s)) for s in sitios) / MB, 1)


def _bases_de(sitios):
    """(bases MariaDB, bases PostgreSQL) de los sitios, según sus metadatos."""
    mariadb, postgres = [], []
    for s in sitios:
        try:
            with open(os.path.join(rutas.META_SITIOS, f"{s}.json")) as f:
                meta = json.load(f)
        except (OSError, ValueError):
            continue
        if meta.get("bd") and RE_BASE.match(str(meta["bd"])):
            mariadb.append(meta["bd"])
        for b in meta.get("bases", []):
            if RE_BASE.match(str(b.get("nombre", ""))):
                (postgres if b.get("motor") == "postgresql" else mariadb).append(b["nombre"])
    return mariadb, postgres


def _numero(orden, sql):
    """Ejecuta una consulta de tamaño; si el motor no está, 0 (no hay bases que medir)."""
    try:
        r = subprocess.run(orden, input=sql, capture_output=True, text=True, timeout=60, cwd="/tmp",
                           env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"})
    except (OSError, subprocess.TimeoutExpired):
        return 0
    try:
        return int(float((r.stdout or "0").strip() or "0")) if r.returncode == 0 else 0
    except ValueError:
        return 0


def bases_mb(sitios):
    mariadb, postgres = _bases_de(sitios)
    total = 0
    # Los nombres ya pasaron RE_BASE (solo [a-z0-9_]): se pueden poner entre comillas sin más.
    if mariadb and os.path.exists(rutas.MARIADB):
        lista = ",".join(f"'{b}'" for b in mariadb)
        total += _numero([rutas.MARIADB, "--protocol=socket", "-u", "root", "-N", "-B"],
                         "SELECT COALESCE(SUM(data_length + index_length), 0) FROM information_schema.tables "
                         f"WHERE table_schema IN ({lista});")
    if postgres and os.path.exists(rutas.PSQL):
        lista = ",".join(f"'{b}'" for b in postgres)
        total += _numero([rutas.RUNUSER, "-u", "postgres", "--", rutas.PSQL, "-X", "-A", "-t", "-q", "-d", "postgres"],
                         f"SELECT COALESCE(SUM(pg_database_size(datname)), 0) FROM pg_database WHERE datname IN ({lista});")
    return round(total / MB, 1)


def uso(dominio, sitios=None, con_bases=True):
    sitios = alcance.sitios_de(dominio) if sitios is None else sitios
    datos = {"sitios": len(sitios), "disco_mb": disco_mb(sitios)}
    if con_bases:
        datos["bases_mb"] = bases_mb(sitios)
    return datos


# --- Comprobaciones antes de cada orden que hace crecer algo ---


def comprobar_sitios(dominio):
    limite = de(dominio)["max_sitios"]
    if len(alcance.sitios_de(dominio)) >= limite:
        raise ErrorPortal(409, f"Ya tiene {limite} sitio(s) en {dominio}, el máximo que le asignaron. "
                               "Para más, hable con el administrador del servidor.")


def comprobar_disco(dominio, extra_bytes=0):
    limite = de(dominio)["disco_mb"]
    ocupado = disco_mb(alcance.sitios_de(dominio))
    if ocupado + extra_bytes / MB > limite:
        raise ErrorPortal(409, f"Sin espacio: los sitios de {dominio} ocupan {ocupado:.0f} MB de {limite} MB. "
                               "Libere espacio o pida más al administrador del servidor.")


def comprobar_bases(dominio, extra_bytes=0):
    limite = de(dominio)["bases_mb"]
    ocupado = bases_mb(alcance.sitios_de(dominio))
    if ocupado + extra_bytes / MB > limite:
        raise ErrorPortal(409, f"Sin espacio para bases de datos: las de {dominio} ocupan {ocupado:.0f} MB "
                               f"de {limite} MB. Pida más al administrador del servidor.")
