"""CPU y memoria de cada sitio (v1.11), medidos cada 5 minutos por el temporizador sitios-recursos.

Lo que gasta un sitio es lo que gasta su usuario de sistema:
- su aplicación propia Python o Node, si la tiene: su unidad de systemd (sitio-<usuario>.service), leída de su
  grupo de control (cgroup v2: cpu.stat y memory.current), que es exacto;
- el resto (el pool de PHP-FPM del sitio, sus tareas programadas, el FTP): todos los procesos de ese usuario,
  leídos de /proc. Los pools de PHP-FPM comparten el grupo de control del servicio php-fpm, así que se cuentan
  por usuario: la memoria es la PSS (la parte de las páginas compartidas que le toca a cada proceso) y la CPU la
  diferencia entre dos lecturas de cada proceso. Lo que gaste un proceso que nace y muere entre dos lecturas no
  se ve: es una medida orientativa, suficiente para ver qué sitio carga el servidor.

Cada sitio guarda un punto por lectura en DIR/<dominio>.json, de las últimas 24 horas: [hora, % de CPU, MB].
Un 100 % de CPU es un núcleo entero. Es ligero: una pasada por /proc cada 5 minutos, sin servicio residente.
"""

import json
import os
import pwd
import time

from comun import leer_meta, todos_los_meta

DIR = "/var/lib/maquita-sitios/recursos"
PROC = "/proc"
CGROUP = "/sys/fs/cgroup/system.slice"
INTERVALO = 300
VENTANA = 24 * 3600
TICKS = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
# Límites de serie (plantillas.py y propias_servicio.py), para enseñarlos junto al uso.
PHP_PROCESOS = 6
PHP_MEMORIA_MB = 256
APP_MEMORIA_MB = 768
APP_CPU = 150


def _escribir(ruta, datos):
    os.makedirs(DIR, mode=0o700, exist_ok=True)
    tmp = ruta + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600), "w") as f:
        json.dump(datos, f, separators=(",", ":"))
    os.replace(tmp, ruta)


def _leer(ruta, defecto):
    try:
        with open(ruta) as f:
            datos = json.load(f)
        return datos if isinstance(datos, type(defecto)) else defecto
    except (OSError, ValueError):
        return defecto


def _texto(ruta):
    try:
        with open(ruta) as f:
            return f.read()
    except OSError:
        return ""


# --- Lectura del sistema ---


def _proceso(pid):
    """(uid, arranque, ticks de CPU, KB de memoria) de un proceso, o None si ya no está."""
    try:
        uid = os.stat(os.path.join(PROC, pid)).st_uid
        stat = _texto(os.path.join(PROC, pid, "stat"))
        campos = stat[stat.rindex(")") + 2:].split()
        ticks, arranque = int(campos[11]) + int(campos[12]), int(campos[19])
    except (OSError, ValueError, IndexError):
        return None
    kb = None
    for linea in _texto(os.path.join(PROC, pid, "smaps_rollup")).splitlines():
        if linea.startswith("Pss:"):
            kb = int(linea.split()[1])
            break
    if kb is None:  # núcleos sin smaps_rollup: la memoria residente
        try:
            kb = int(_texto(os.path.join(PROC, pid, "statm")).split()[1]) * (os.sysconf("SC_PAGE_SIZE") // 1024)
        except (ValueError, IndexError):
            kb = 0
    return uid, arranque, ticks, kb


def _procesos(uids):
    """{uid: {pid: (arranque, ticks, kb)}} solo de los usuarios de los sitios."""
    salida = {u: {} for u in uids}
    try:
        nombres = os.listdir(PROC)
    except OSError:
        return salida
    for pid in nombres:
        if not pid.isdigit():
            continue
        datos = _proceso(pid)
        if datos and datos[0] in salida:
            salida[datos[0]][pid] = datos[1:]
    return salida


def _unidad(usuario):
    """{pids, usec, bytes} de la unidad de la aplicación propia, o None si no corre."""
    carpeta = os.path.join(CGROUP, f"sitio-{usuario}.service")
    if not os.path.isdir(carpeta):
        return None
    usec = 0
    for linea in _texto(os.path.join(carpeta, "cpu.stat")).splitlines():
        if linea.startswith("usage_usec "):
            usec = int(linea.split()[1])
    try:
        memoria = int(_texto(os.path.join(carpeta, "memory.current")).strip() or 0)
    except ValueError:
        memoria = 0
    pids = set(_texto(os.path.join(carpeta, "cgroup.procs")).split())
    return {"pids": pids, "usec": usec, "bytes": memoria}


# --- Recolector (temporizador) ---


def _medir(usuario, procesos, previos, unidad, unidad_previa, segundos):
    """(% de CPU o None, MB) de un sitio entre la lectura anterior y esta."""
    fuera = unidad["pids"] if unidad else set()
    ticks, kb = 0, 0
    for pid, (arranque, t, k) in procesos.items():
        if pid in fuera:
            continue
        kb += k
        antes = previos.get(pid)
        ticks += t - antes[1] if antes and antes[0] == arranque and t >= antes[1] else t
    cpu_s = ticks / TICKS
    mb = kb / 1024
    if unidad:
        mb += unidad["bytes"] / 1048576
        if unidad_previa is not None and unidad["usec"] >= unidad_previa:
            cpu_s += (unidad["usec"] - unidad_previa) / 1e6
        elif unidad_previa is None:
            segundos = None  # la aplicación acaba de arrancar: sin referencia para su CPU
    if not segundos or segundos <= 0 or segundos > 3 * INTERVALO:
        return None, round(mb, 1)
    return round(min(cpu_s / segundos * 100, 6400.0), 1), round(mb, 1)


def recoger(ahora=None):
    """recursos-recoger: un punto por sitio y limpieza de los sitios que ya no están."""
    ahora = int(ahora or time.time())
    estado = _leer(os.path.join(DIR, "estado.json"), {})
    segundos = ahora - int(estado.get("ts") or 0) if estado.get("ts") else None
    metas = todos_los_meta()
    usuarios = {}
    for m in metas:
        try:
            usuarios[m["dominio"]] = (m["usuario"], pwd.getpwnam(m["usuario"]).pw_uid)
        except (KeyError, TypeError):
            continue
    todos = _procesos({uid for _u, uid in usuarios.values()})
    nuevo = {"ts": ahora, "procesos": {}, "unidades": {}}
    medidos = []
    for dominio, (usuario, uid) in usuarios.items():
        unidad = _unidad(usuario)
        previos = {p: tuple(v) for p, v in (estado.get("procesos", {}).get(usuario) or {}).items()}
        cpu, mb = _medir(usuario, todos.get(uid, {}), previos, unidad, (estado.get("unidades") or {}).get(usuario),
                         segundos)
        nuevo["procesos"][usuario] = {p: [a, t] for p, (a, t, _k) in todos.get(uid, {}).items()}
        if unidad:
            nuevo["unidades"][usuario] = unidad["usec"]
        ruta = os.path.join(DIR, f"{dominio}.json")
        serie = _leer(ruta, {"puntos": []})
        puntos = [p for p in serie.get("puntos", []) if isinstance(p, list) and len(p) == 3 and p[0] > ahora - VENTANA]
        puntos.append([ahora, cpu, mb])
        _escribir(ruta, {"puntos": puntos})
        medidos.append(dominio)
    _escribir(os.path.join(DIR, "estado.json"), nuevo)
    borrados = _huerfanos(set(usuarios))
    return {"medidos": len(medidos), "borrados": borrados}


def _huerfanos(dominios):
    """Series de sitios dados de baja."""
    borrados = []
    try:
        nombres = os.listdir(DIR)
    except OSError:
        return borrados
    for n in nombres:
        if n.endswith(".json") and n != "estado.json" and n[:-5] not in dominios:
            os.remove(os.path.join(DIR, n))
            borrados.append(n[:-5])
    return borrados


# --- Consulta (panel y portal) ---


def _limites(meta):
    ajustes = meta.get("php_ajustes") or {}
    try:
        memoria_php = int(str(ajustes.get("memory_limit") or PHP_MEMORIA_MB).rstrip("Mm"))
    except ValueError:
        memoria_php = PHP_MEMORIA_MB
    limites = {"php_procesos": PHP_PROCESOS, "php_memoria_mb": memoria_php}
    if (meta.get("propia") or {}).get("tipo") in ("python", "node"):
        limites.update(app_memoria_mb=APP_MEMORIA_MB, app_cpu=APP_CPU)
    return limites


def ver(dominio):
    """recursos <dominio>: los puntos de las últimas 24 h, un resumen y los límites del sitio."""
    meta = leer_meta(dominio)
    ahora = int(time.time())
    puntos = [p for p in _leer(os.path.join(DIR, f"{dominio}.json"), {"puntos": []}).get("puntos", [])
              if isinstance(p, list) and len(p) == 3 and p[0] > ahora - VENTANA]
    cpus = [p[1] for p in puntos if isinstance(p[1], (int, float))]
    mems = [p[2] for p in puntos if isinstance(p[2], (int, float))]
    resumen = {
        "cpu_media": round(sum(cpus) / len(cpus), 1) if cpus else None, "cpu_maxima": max(cpus) if cpus else None,
        "memoria_media_mb": round(sum(mems) / len(mems), 1) if mems else None,
        "memoria_maxima_mb": max(mems) if mems else None,
        "ultimo": puntos[-1] if puntos else None,
    }
    # Sin la carpeta, el temporizador no está instalado (ajuste 69): la pantalla lo dice en vez de un gráfico vacío.
    return {"dominio": dominio, "instalado": os.path.isdir(DIR), "intervalo": INTERVALO, "puntos": puntos,
            "resumen": resumen, "limites": _limites(meta)}
