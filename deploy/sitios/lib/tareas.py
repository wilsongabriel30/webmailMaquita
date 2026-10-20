"""Trabajos de cron de un sitio: órdenes o scripts que se ejecutan solos a una hora, como el cron de cPanel.

Cada trabajo es un temporizador de systemd (no hace falta el demonio cron) que ejecuta la orden con el usuario
del sitio y el mismo encierro que las aplicaciones propias: solo escribe en su carpeta pública y su carpeta
privada, sin privilegios, con límites de memoria, CPU y una hora como máximo. El horario se escribe como en
cron («*/15 * * * *») y se traduce al calendario de systemd. La salida de cada ejecución va a
registros/cron-<id>.log, que el panel muestra.
"""

import os
import re
import secrets
import subprocess

from comun import ErrorSitio, ejecutar, guardar_meta, leer_meta

MAXIMO = 20
UNIDADES = "/etc/systemd/system"
DIAS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
NOMBRES_DIAS = {"sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6}
NOMBRES_MESES = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
ATAJOS = {"@hourly": "0 * * * *", "@daily": "0 0 * * *", "@midnight": "0 0 * * *", "@weekly": "0 0 * * 0",
          "@monthly": "0 0 1 * *", "@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *"}
RE_ID = re.compile(r"^[0-9a-f]{8}$")


def _campo(texto, minimo, maximo, nombres=None):
    """Un campo de cron → su forma en el calendario de systemd. «*», números, listas, rangos y pasos."""
    partes = []
    for parte in texto.split(","):
        base, _, paso = parte.partition("/")
        if paso and not paso.isdigit():
            raise ErrorSitio(f"paso no válido: {parte}")
        if base == "*":
            partes.append(f"{minimo}/{paso}" if paso else "*")
            continue
        inicio, _, fin = base.partition("-")
        valores = []
        for v in (inicio, fin) if fin else (inicio,):
            v = v.lower()
            n = (nombres or {}).get(v, v)
            if not str(n).isdigit() or not minimo <= int(n) <= maximo:
                raise ErrorSitio(f"valor fuera de rango: {parte} ({minimo}–{maximo})")
            valores.append(int(n))
        if paso and fin:
            partes.extend(str(x) for x in range(valores[0], valores[1] + 1, int(paso)))
        elif paso:
            partes.append(f"{valores[0]}/{paso}")
        elif fin:
            if valores[1] < valores[0]:
                raise ErrorSitio(f"rango al revés: {parte}")
            partes.append(f"{valores[0]}..{valores[1]}")
        else:
            partes.append(str(valores[0]))
    return ",".join(partes)


def _dias_semana(texto):
    if texto == "*":
        return ""
    dias = []
    for parte in texto.split(","):
        if "/" in parte:
            raise ErrorSitio("los pasos («/») no se admiten en el día de la semana")
        inicio, _, fin = parte.partition("-")
        a = NOMBRES_DIAS.get(inicio.lower(), inicio)
        b = NOMBRES_DIAS.get(fin.lower(), fin) if fin else a
        if not (str(a).isdigit() and str(b).isdigit() and 0 <= int(a) <= 7 and 0 <= int(b) <= 7):
            raise ErrorSitio(f"día de la semana no válido: {parte} (0–7 o sun–sat)")
        a, b = int(a), int(b)
        dias.append(DIAS[a] if a == b else f"{DIAS[a]}..{DIAS[b]}")
    return ",".join(dias) + " "


def calendario(horario):
    """«m h dom mes dow» (o @daily…) → OnCalendar de systemd, comprobado con systemd-analyze."""
    horario = " ".join(str(horario or "").split())
    horario = ATAJOS.get(horario, horario)
    campos = horario.split(" ")
    if len(campos) != 5 or not all(re.fullmatch(r"[0-9a-zA-Z*,/-]{1,60}", c) for c in campos):
        raise ErrorSitio("horario no válido: escriba cinco campos (minuto hora día mes día-de-la-semana), p. ej. «0 3 * * *»")
    minuto, hora, dia, mes, semana = campos
    if dia != "*" and semana != "*":
        # cron lo entiende como «o»; systemd como «y». Mejor no adivinar.
        raise ErrorSitio("indique el día del mes o el día de la semana, no los dos")
    texto = (f"{_dias_semana(semana)}*-{_campo(mes, 1, 12, NOMBRES_MESES)}-{_campo(dia, 1, 31)} "
             f"{_campo(hora, 0, 23)}:{_campo(minuto, 0, 59)}:00")
    r = subprocess.run(["systemd-analyze", "calendar", texto], capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise ErrorSitio(f"horario no válido: {horario}")
    siguiente = re.search(r"Next elapse:\s*(.+)", r.stdout)
    return texto, (siguiente.group(1).strip() if siguiente else None)


def _orden(valor):
    valor = str(valor or "").strip()
    if not 1 <= len(valor) <= 1000 or re.search(r"[\x00-\x1f\x7f]", valor):
        raise ErrorSitio("la orden debe tener entre 1 y 1000 caracteres, en una sola línea")
    return valor


def _nombre(meta, tarea_id):
    return f"sitio-{meta['usuario']}-cron-{tarea_id}"


def _registro(meta, tarea_id):
    return os.path.join(meta["registros"], f"cron-{tarea_id}.log")


def _unidades(meta, t):
    servicio = f"""# Generado por maquita-sitios (trabajo de cron del sitio {meta['dominio']}). No editar a mano.
[Unit]
Description=Trabajo de cron de {meta['dominio']}: {t['descripcion'] or t['id']}

[Service]
Type=oneshot
User={meta['usuario']}
Group={meta['usuario']}
WorkingDirectory={meta['publico']}
Environment=HOME={meta['tmp']} TMPDIR={meta['tmp']}
ExecStart=/bin/sh -c {_comillas(t['orden'])}
StandardOutput=append:{_registro(meta, t['id'])}
StandardError=append:{_registro(meta, t['id'])}
UMask=0027
RuntimeMaxSec=3600
Nice=10
IOSchedulingClass=idle

NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths={meta['publico']} {meta['tmp']}
InaccessiblePaths=-/etc/maquita-sitios -/srv/sitios-papelera -/etc/maquita-cortafuegos -/etc/maquita-respaldos
ProtectHome=yes
PrivateTmp=yes
PrivateDevices=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectKernelLogs=yes
ProtectControlGroups=yes
ProtectClock=yes
ProtectHostname=yes
ProtectProc=invisible
RestrictNamespaces=yes
RestrictRealtime=yes
RestrictSUIDSGID=yes
LockPersonality=yes
SystemCallArchitectures=native
RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX
SocketBindDeny=any
CapabilityBoundingSet=
MemoryMax=512M
CPUQuota=100%
TasksMax=64
"""
    temporizador = f"""# Generado por maquita-sitios. No editar a mano.
[Unit]
Description=Horario del trabajo de cron {t['id']} de {meta['dominio']}

[Timer]
OnCalendar={t['calendario']}
AccuracySec=1s
Persistent=false

[Install]
WantedBy=timers.target
"""
    return servicio, temporizador


def _comillas(texto):
    """Comillas de systemd para un único argumento («%» y «$» se escapan para que lleguen tal cual)."""
    return '"' + texto.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%").replace("$", "$$") + '"'


def _escribir_unidades(meta):
    """Deja en systemd exactamente los trabajos del sitio (crea, cambia y quita)."""
    prefijo = f"sitio-{meta['usuario']}-cron-"
    deseados = {}
    for t in meta.get("cron", []):
        servicio, temporizador = _unidades(meta, t)
        deseados[_nombre(meta, t["id"])] = (servicio, temporizador, t.get("activo", True))
    for archivo in os.listdir(UNIDADES):
        if archivo.startswith(prefijo) and archivo.endswith(".timer") and archivo[:-6] not in deseados:
            ejecutar(["systemctl", "disable", "--now", archivo])
            os.remove(os.path.join(UNIDADES, archivo))
            servicio = os.path.join(UNIDADES, archivo[:-6] + ".service")
            if os.path.exists(servicio):
                os.remove(servicio)
    for nombre, (servicio, temporizador, _) in deseados.items():
        for extension, texto in ((".service", servicio), (".timer", temporizador)):
            with open(os.path.join(UNIDADES, nombre + extension), "w") as f:
                f.write(texto)
    ejecutar(["systemctl", "daemon-reload"])
    for nombre, (_, _, activo) in deseados.items():
        ejecutar(["systemctl", "enable" if activo else "disable", "--now", nombre + ".timer"])
        if activo:
            ejecutar(["systemctl", "restart", nombre + ".timer"])  # toma el horario nuevo


def _publica(meta, t):
    r = subprocess.run(["systemctl", "show", _nombre(meta, t["id"]) + ".service", "-p", "Result,ExecMainStatus,"
                        "ExecMainExitTimestamp,ActiveState"], capture_output=True, text=True, timeout=30)
    estado = dict(linea.split("=", 1) for linea in r.stdout.splitlines() if "=" in linea)
    siguiente = calendario(t["horario"])[1] if t.get("activo", True) else None
    return {**{k: t[k] for k in ("id", "horario", "orden", "descripcion")}, "activo": t.get("activo", True),
            "siguiente": siguiente, "ultima": estado.get("ExecMainExitTimestamp") or None,
            "en_curso": estado.get("ActiveState") == "activating",
            "resultado": None if not estado.get("ExecMainExitTimestamp") else
            ("correcto" if estado.get("Result") == "success" else f"falló (código {estado.get('ExecMainStatus')})")}


def listar(dominio):
    meta = leer_meta(dominio)
    return {"dominio": dominio, "usuario": meta["usuario"], "carpeta": meta["publico"],
            "php": f"/usr/bin/php{meta.get('php') or ''}", "trabajos": [_publica(meta, t) for t in meta.get("cron", [])]}


def guardar(dominio, lista):
    """Reemplaza la lista de trabajos del sitio (el panel manda la lista completa)."""
    meta = leer_meta(dominio)
    if not isinstance(lista, list) or len(lista) > MAXIMO:
        raise ErrorSitio(f"se admiten hasta {MAXIMO} trabajos por sitio")
    anteriores = {t["id"]: t for t in meta.get("cron", [])}
    nuevos = []
    for dato in lista:
        if not isinstance(dato, dict):
            raise ErrorSitio("trabajo no válido")
        tarea_id = dato.get("id") if dato.get("id") in anteriores else secrets.token_hex(4)
        descripcion = str(dato.get("descripcion") or "").strip()[:80]
        if re.search(r"[\x00-\x1f\x7f<>]", descripcion):
            raise ErrorSitio("la descripción no admite < > ni caracteres de control")
        cal, _ = calendario(dato.get("horario"))
        nuevos.append({"id": tarea_id, "horario": " ".join(str(dato["horario"]).split()), "calendario": cal,
                       "orden": _orden(dato.get("orden")), "descripcion": descripcion,
                       "activo": bool(dato.get("activo", True))})
    meta["cron"] = nuevos
    guardar_meta(meta)
    _escribir_unidades(meta)
    for tarea_id in set(anteriores) - {t["id"] for t in nuevos}:
        if os.path.exists(_registro(meta, tarea_id)):
            os.remove(_registro(meta, tarea_id))
    return listar(dominio)


def _buscar(meta, tarea_id):
    if not RE_ID.match(tarea_id or ""):
        raise ErrorSitio("trabajo no válido")
    for t in meta.get("cron", []):
        if t["id"] == tarea_id:
            return t
    raise ErrorSitio("ese trabajo no existe")


def ejecutar_ahora(dominio, tarea_id):
    meta = leer_meta(dominio)
    t = _buscar(meta, tarea_id)
    ejecutar(["systemctl", "start", "--no-block", _nombre(meta, t["id"]) + ".service"])
    return {"dominio": dominio, "id": tarea_id, "lanzado": True}


def registro(dominio, tarea_id, lineas=200):
    meta = leer_meta(dominio)
    t = _buscar(meta, tarea_id)
    ruta = _registro(meta, t["id"])
    if not os.path.exists(ruta):
        return {"id": tarea_id, "registro": ""}
    with open(ruta, "rb") as f:
        f.seek(0, os.SEEK_END)
        f.seek(max(0, f.tell() - 64 * 1024))
        texto = f.read().decode("utf-8", "replace")
    return {"id": tarea_id, "registro": "\n".join(texto.splitlines()[-lineas:])}


def quitar_todos(meta):
    """Al dar de baja el sitio."""
    if meta.get("cron"):
        meta["cron"] = []
        _escribir_unidades(meta)
