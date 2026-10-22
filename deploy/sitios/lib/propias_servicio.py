"""Piezas de sistema de las aplicaciones propias Python y Node.js: puertos, dependencias, unidad de
systemd encerrada y apertura de puertos públicos en el cortafuegos del servidor."""

import json
import os
import re
import subprocess

from comun import ErrorSitio, ejecutar, todos_los_meta

PUERTOS_INTERNOS = range(20000, 30000)
# Puertos que ninguna aplicación puede pedir como públicos: los del correo, la web, el panel, el FTP
# pasivo y los internos de las aplicaciones.
RESERVADOS = {21, 22, 25, 53, 80, 110, 143, 443, 465, 587, 993, 995, 4190, 8000, 8001, 8443}
CORTAFUEGOS_APPS = "/etc/maquita-cortafuegos/apps.d"
CORTAFUEGOS = "/usr/local/sbin/maquita-cortafuegos"
ENTORNO_DIR = "/etc/maquita-sitios/entorno"
RE_VARIABLE = re.compile(r"^[A-Z_][A-Z0-9_]{0,63}$")
# Las pone el panel: no se pueden sobrescribir desde las variables de entorno.
VARIABLES_PROPIAS = {"PORT", "HOST", "PUERTO_PUBLICO", "HOME", "PATH", "NODE_ENV", "PYTHONUNBUFFERED"}


def unidad(meta):
    return f"sitio-{meta['usuario']}"


def ruta_unidad(meta):
    return f"/etc/systemd/system/{unidad(meta)}.service"


def ruta_entorno(meta):
    return os.path.join(ENTORNO_DIR, f"{meta['dominio']}.env")


def ruta_venv(meta):
    return os.path.join(meta["base"], "entorno")


def _escuchando():
    r = subprocess.run(["ss", "-Hlntu"], capture_output=True, text=True, timeout=10)
    puertos = set()
    for linea in r.stdout.splitlines():
        partes = linea.split()
        if len(partes) >= 5:
            m = re.search(r":(\d+)$", partes[4])
            if m:
                puertos.add(int(m.group(1)))
    return puertos


def _usados_por_apps(excepto=None):
    usados = set()
    for m in todos_los_meta():
        p = m.get("propia") or {}
        if m["dominio"] != excepto:
            usados.update(x for x in (p.get("puerto"), p.get("puerto_publico")) if x)
    return usados


def puerto_interno(meta):
    ocupados = _escuchando() | _usados_por_apps()
    for puerto in PUERTOS_INTERNOS:
        if puerto not in ocupados:
            return puerto
    raise ErrorSitio("no quedan puertos internos libres para aplicaciones")


def validar_puerto_publico(dominio, puerto):
    if not isinstance(puerto, int) or not 1024 <= puerto <= 65535:
        raise ErrorSitio("el puerto público debe estar entre 1024 y 65535")
    if puerto in RESERVADOS or puerto in PUERTOS_INTERNOS or 40000 <= puerto <= 40100:
        raise ErrorSitio(f"el puerto {puerto} está reservado para los servicios del servidor")
    if puerto in _usados_por_apps(excepto=dominio) or puerto in _escuchando():
        raise ErrorSitio(f"el puerto {puerto} ya está en uso")
    return puerto


def _entorno_usuario(meta):
    """Cachés de pip y npm en la carpeta privada del sitio (el usuario no tiene carpeta personal)."""
    return {"HOME": meta["tmp"], "PIP_CACHE_DIR": os.path.join(meta["tmp"], ".cache-pip"),
            "npm_config_cache": os.path.join(meta["tmp"], ".npm"), "npm_config_update_notifier": "false",
            "npm_config_fund": "false", "npm_config_audit": "false"}


def dependencias(meta):
    """Python: entorno virtual propio con requirements.txt + gunicorn (y uvicorn si es ASGI).
    Node: «npm ci» (o «npm install» sin package-lock.json), sin dependencias de desarrollo."""
    propia, app, usuario = meta["propia"], meta["app_dir"], meta["usuario"]
    extra = _entorno_usuario(meta)
    if propia["tipo"] == "python":
        venv = ruta_venv(meta)
        if not os.path.exists(os.path.join(venv, "bin", "python")):
            os.makedirs(venv, exist_ok=True)
            ejecutar(["chown", f"{usuario}:{usuario}", venv])
            ejecutar(["python3", "-m", "venv", venv], como=usuario, env_extra=extra)
        pip = [os.path.join(venv, "bin", "pip"), "install", "--disable-pip-version-check", "-q"]
        if os.path.isfile(os.path.join(app, "requirements.txt")):
            ejecutar(pip + ["-r", "requirements.txt"], como=usuario, cwd=app, tiempo=900, env_extra=extra)
        servidores = ["gunicorn"] + (["uvicorn"] if propia.get("modo") == "asgi" else [])
        ejecutar(pip + servidores, como=usuario, cwd=app, tiempo=600, env_extra=extra)
    elif propia["tipo"] == "node" and os.path.isfile(os.path.join(app, "package.json")):
        orden = "ci" if os.path.isfile(os.path.join(app, "package-lock.json")) else "install"
        ejecutar(["npm", orden, "--omit=dev", "--no-audit", "--no-fund"], como=usuario, cwd=app, tiempo=900,
                 env_extra=extra)


def _orden_inicio(meta):
    propia, app = meta["propia"], meta["app_dir"]
    if propia["tipo"] == "python":
        orden = [os.path.join(ruta_venv(meta), "bin", "gunicorn"), "--bind", f"127.0.0.1:{propia['puerto']}",
                 "--workers", "2", "--timeout", "120", "--access-logfile", "-", "--chdir", app]
        if propia.get("modo") == "asgi":
            orden += ["--worker-class", "uvicorn.workers.UvicornWorker"]
        return " ".join(orden + [propia["entrada"]])
    if propia["entrada"] == "npm start":
        return "/usr/bin/npm start"
    return f"/usr/bin/node {os.path.join(app, propia['entrada'])}"


def texto_unidad(meta):
    propia = meta["propia"]
    variables = [f"PORT={propia['puerto']}", "HOST=127.0.0.1", f"HOME={meta['tmp']}", "PYTHONUNBUFFERED=1",
                 "NODE_ENV=production"]
    enlaces = [f"SocketBindAllow=tcp:{propia['puerto']}"]
    if propia.get("puerto_publico"):
        variables.append(f"PUERTO_PUBLICO={propia['puerto_publico']}")
        enlaces.append(f"SocketBindAllow={propia.get('protocolo', 'tcp')}:{propia['puerto_publico']}")
    return f"""# Generado por maquita-sitios. No editar a mano: el panel lo regenera.
[Unit]
Description=Aplicación propia de {meta['dominio']}
After=network-online.target mariadb.service postgresql.service
Wants=network-online.target

[Service]
Type=simple
User={meta['usuario']}
Group={meta['usuario']}
WorkingDirectory={meta['app_dir']}
EnvironmentFile=-{ruta_entorno(meta)}
Environment={' '.join(variables)}
ExecStart={_orden_inicio(meta)}
Restart=on-failure
RestartSec=5
UMask=0027

# Encierro: solo escribe en su código y en su carpeta privada; solo abre sus propios puertos.
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths={meta['app_dir']} {meta['tmp']}
# La clave o la credencial del repositorio (despliegues/) son para git, no para la aplicación en marcha.
InaccessiblePaths=-/etc/maquita-sitios -/srv/sitios-papelera -/etc/maquita-cortafuegos -{os.path.join(meta['base'], 'despliegues')}
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
{chr(10).join(enlaces)}
SocketBindDeny=any
CapabilityBoundingSet=
MemoryMax=768M
CPUQuota=150%
TasksMax=256

[Install]
WantedBy=multi-user.target
"""


def instalar_unidad(meta):
    with open(ruta_unidad(meta), "w") as f:
        f.write(texto_unidad(meta))
    ejecutar(["systemctl", "daemon-reload"])
    ejecutar(["systemctl", "enable", unidad(meta)])


def quitar_unidad(meta):
    for orden in (["systemctl", "disable", "--now", unidad(meta)], ["systemctl", "reset-failed", unidad(meta)]):
        subprocess.run(orden, capture_output=True, timeout=60)
    for ruta in (ruta_unidad(meta), ruta_entorno(meta)):
        if os.path.exists(ruta):
            os.remove(ruta)
    subprocess.run(["systemctl", "daemon-reload"], capture_output=True, timeout=60)


def systemctl(meta, accion):
    ejecutar(["systemctl", accion, unidad(meta)], tiempo=120)


def _responde(meta):
    """¿La aplicación contesta por HTTP? Cualquier código vale (también 404 o 500): lo que importa es que
    haya un proceso atendiendo. gunicorn abre el puerto aunque sus trabajadores no lleguen a arrancar."""
    import http.client

    conexion = http.client.HTTPConnection("127.0.0.1", meta["propia"]["puerto"], timeout=5)
    try:
        conexion.request("GET", "/", headers={"Host": meta["dominio"], "User-Agent": "maquita-sitios"})
        return conexion.getresponse().status > 0
    except (OSError, http.client.HTTPException):
        return False
    finally:
        conexion.close()


def esperar_activo(meta, segundos=30):
    """Tras arrancar: el servicio debe seguir activo y contestar en su puerto."""
    import time

    limite = time.time() + segundos
    while time.time() < limite:
        time.sleep(1)
        activo = subprocess.run(["systemctl", "is-active", unidad(meta)], capture_output=True, text=True).stdout.strip()
        if activo == "failed":
            break
        if activo == "active" and meta["propia"]["puerto"] in _escuchando() and _responde(meta):
            return True
    raise ErrorSitio("la aplicación no arrancó; revise los registros en «Gestionar»:\n" + registros(meta, 15))


def registros(meta, lineas=100):
    r = subprocess.run(["journalctl", "-u", unidad(meta), "-n", str(lineas), "--no-pager", "-o", "short-iso"],
                       capture_output=True, text=True, timeout=30)
    return r.stdout[-20000:]


# --- Variables de entorno ---


def leer_entorno(meta):
    variables = {}
    try:
        with open(ruta_entorno(meta)) as f:
            for linea in f:
                clave, _, valor = linea.rstrip("\n").partition("=")
                if RE_VARIABLE.match(clave):
                    variables[clave] = json.loads(valor) if valor.startswith('"') else valor
    except FileNotFoundError:
        pass
    return variables


def guardar_entorno(meta, variables):
    os.makedirs(ENTORNO_DIR, mode=0o700, exist_ok=True)
    ruta = ruta_entorno(meta)
    tmp = ruta + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
        for clave, valor in sorted(variables.items()):
            # Comillas dobles con «\» y «"» escapados: la forma que systemd entiende en EnvironmentFile.
            f.write(f"{clave}={json.dumps(valor, ensure_ascii=False)}\n")
    os.replace(tmp, ruta)


# --- Cortafuegos ---


def abrir_puerto(meta):
    """Registra el puerto público para el cortafuegos del servidor y le pide recargar sus reglas."""
    propia = meta["propia"]
    os.makedirs(CORTAFUEGOS_APPS, mode=0o700, exist_ok=True)
    ruta = os.path.join(CORTAFUEGOS_APPS, f"{meta['dominio']}.json")
    with open(os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
        json.dump({"dominio": meta["dominio"], "puertos": str(propia["puerto_publico"]),
                   "protocolo": propia.get("protocolo", "tcp")}, f)
    return _recargar_cortafuegos()


def cerrar_puerto(meta):
    ruta = os.path.join(CORTAFUEGOS_APPS, f"{meta['dominio']}.json")
    if os.path.exists(ruta):
        os.remove(ruta)
        return _recargar_cortafuegos()
    return None


def _recargar_cortafuegos():
    if not os.path.exists(CORTAFUEGOS):
        return "sin cortafuegos propio (el puerto queda como lo tenga el sistema)"
    r = subprocess.run([CORTAFUEGOS, "recargar"], capture_output=True, text=True, timeout=60)
    try:
        datos = json.loads(r.stdout)
    except ValueError:
        raise ErrorSitio("el cortafuegos no respondió al recargar sus reglas")
    if datos.get("error"):
        raise ErrorSitio(f"cortafuegos: {datos['error']}")
    return "aplicado" if datos.get("recargado") else "cortafuegos inactivo"
