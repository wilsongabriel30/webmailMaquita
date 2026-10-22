"""De dónde lee el recolector: archivos de registro (por posición), el diario de systemd (por cursor)
y la auditoría del webmail y del panel (por último id). Cada lectura devuelve lo nuevo y el estado
con el que seguir en la próxima pasada; nunca relee lo ya contado.
"""

from __future__ import annotations

import os
import re
import subprocess

# Primera pasada sobre un archivo: solo los últimos bytes (no recorrer meses de registro de golpe).
INICIO_BYTES = 5 * 1024 * 1024
MAXIMO_BYTES = 64 * 1024 * 1024  # por pasada y por archivo; lo que sobre se lee en la siguiente
_RE_CURSOR = re.compile(r"-- cursor: (\S{1,500})")


def _leer_desde(ruta: str, desde: int, maximo: int) -> tuple:
    with open(ruta, "rb") as f:
        f.seek(desde)
        datos = f.read(maximo)
    # Solo líneas completas: la última a medias se lee en la próxima pasada.
    corte = datos.rfind(b"\n")
    if corte < 0:
        return [], desde
    util = datos[: corte + 1]
    return util.decode("utf-8", "replace").splitlines(), desde + len(util)


def leer_archivo(ruta: str, estado: dict | None, rotado: str | None = None, maximo: int = MAXIMO_BYTES) -> tuple:
    """Líneas nuevas de `ruta` y el estado {"inodo", "pos"} para la próxima vez.

    Si el archivo rotó (otro inodo o más corto que la posición guardada), primero se termina el
    rotado (`ruta.1`) desde donde se quedó, si sigue ahí con el mismo inodo, y luego el nuevo desde
    el principio."""
    try:
        st = os.stat(ruta)
    except OSError:
        return [], estado or {}
    lineas = []
    if not estado or "inodo" not in estado:
        desde = max(0, st.st_size - INICIO_BYTES)
        nuevas, pos = _leer_desde(ruta, desde, maximo)
        if desde > 0 and nuevas:
            nuevas = nuevas[1:]  # la primera puede estar cortada
        return nuevas, {"inodo": st.st_ino, "pos": pos}
    if estado["inodo"] != st.st_ino or st.st_size < estado.get("pos", 0):
        rot = rotado or ruta + ".1"
        try:
            if os.stat(rot).st_ino == estado["inodo"]:
                viejas, _ = _leer_desde(rot, estado.get("pos", 0), maximo)
                lineas.extend(viejas)
        except OSError:
            pass
        estado = {"inodo": st.st_ino, "pos": 0}
    nuevas, pos = _leer_desde(ruta, estado.get("pos", 0), maximo)
    lineas.extend(nuevas)
    return lineas, {"inodo": st.st_ino, "pos": pos}


def leer_diario(cursor: str | None, maximo_lineas: int = 400000, tiempo: int = 180) -> tuple:
    """Correo (facilidad «mail»: Postfix y Dovecot) del diario de systemd desde el cursor guardado.

    Para las instalaciones sin /var/log/mail.log (solo journald)."""
    orden = ["journalctl", "--no-pager", "-q", "-o", "short-iso", "--show-cursor", "SYSLOG_FACILITY=2"]
    if cursor:
        orden += ["--after-cursor", cursor]
    else:
        orden += ["--since", "-15min"]
    try:
        r = subprocess.run(orden, capture_output=True, text=True, timeout=tiempo, errors="replace")
    except (OSError, subprocess.TimeoutExpired):
        return [], cursor
    lineas = r.stdout.splitlines()
    nuevo = cursor
    if lineas:
        m = _RE_CURSOR.fullmatch(lineas[-1].strip())
        if m:
            nuevo = m.group(1)
            lineas = lineas[:-1]
    return lineas[:maximo_lineas], nuevo


def tamano_cola(tiempo: int = 30) -> int | None:
    """Mensajes en la cola de Postfix (una línea JSON por mensaje en «postqueue -j»)."""
    try:
        r = subprocess.run(["postqueue", "-j"], capture_output=True, text=True, timeout=tiempo)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    return sum(1 for linea in r.stdout.splitlines() if linea.startswith("{"))


async def filas_nuevas(db, consulta: str, ultimo_id: int | None, inicial: str, limite: int = 50000) -> tuple:
    """Filas con id mayor que el último leído. La primera vez se parte de `inicial` (una consulta que
    devuelve el id desde el que empezar: p. ej. el último de hace un día)."""
    try:
        if ultimo_id is None:
            ultimo_id = int(await db.fetchval(inicial) or 0)
        filas = await db.fetch(consulta, ultimo_id, limite)
    except Exception:
        return [], ultimo_id  # tabla ausente en esta instalación: se ignora esa fuente
    if filas:
        ultimo_id = max(int(f["id"]) for f in filas)
    return filas, ultimo_id
