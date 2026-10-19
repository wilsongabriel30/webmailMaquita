"""Instalar una versión: lo que UPGRADING.md manda hacer a mano, en orden, con respaldo, comprobación
antes y después, y vuelta a la versión anterior si la nueva deja el servidor peor que estaba.

Pasos: respaldo (versión anterior y volcado de la base) → código (checkout) → migraciones (como el
usuario de la aplicación) → dependencias de cada entorno de Python → frontends (correo y panel) →
secciones instaladas (sitios, DNS, cortafuegos, identidad, actualizaciones) → ajustes del servidor →
reinicio de servicios → validación. Las migraciones son aditivas (IF NOT EXISTS): al volver atrás no se
deshacen, la base no se restaura sola (perdería el correo llegado entretanto); el volcado queda para
hacerlo a mano si hiciera falta.
"""

import glob
import os
import shutil
import subprocess
import time

from version import DIR_ESTADO, REPO, ErrorActualizar, actual, git, guardar_json, leer_json

PROGRESO = os.path.join(DIR_ESTADO, "progreso.json")
HISTORIAL = os.path.join(DIR_ESTADO, "historial.json")
RESPALDOS = "/var/backups/maquita-actualizar"
REGISTROS = "/var/log/maquita-actualizar"
CERROJO = "/run/maquita-actualizar.lock"
ENTORNOS = ("backend", "admin-panel/backend", "panel-dominio/backend", "chat-service", "almacen",
            "almacen/aplicaciones/bi", "almacen/aplicaciones/pdf_editor")
SERVICIOS = ("maquita-webmail", "maquita-admin", "maquita-milter", "maquita-almacen", "maquita-bi",
             "maquita-pdf-editor", "maquita-chat")
SECCIONES = ("sitios", "dns", "cortafuegos", "identidad", "actualizar")


class Proceso:
    def __init__(self, desde, hasta):
        os.makedirs(REGISTROS, mode=0o750, exist_ok=True)
        self.sello = time.strftime("%Y%m%d-%H%M%S")
        self.registro = os.path.join(REGISTROS, f"{self.sello}.log")
        self.estado = {"estado": "en curso", "desde": desde["version"], "desde_commit": desde["commit"],
                       "hasta": hasta["ref"], "hasta_commit": hasta["commit"], "inicio": time.strftime("%Y-%m-%d %H:%M:%S"),
                       "paso": "", "registro": self.registro}

    def paso(self, texto):
        self.estado["paso"] = texto
        guardar_json(PROGRESO, self.estado)
        self.anotar(f"\n== {texto} ==")

    def anotar(self, texto):
        with open(self.registro, "a") as f:
            f.write(texto.rstrip() + "\n")

    def orden(self, cmd, cwd=REPO, tiempo=1800, obligatoria=True, entorno=None):
        self.anotar("$ " + " ".join(cmd))
        env = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8", "HOME": "/root",
               "DEBIAN_FRONTEND": "noninteractive"}
        env.update(entorno or {})
        with open(self.registro, "a") as f:
            r = subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT, timeout=tiempo, env=env)
        if r.returncode != 0 and obligatoria:
            raise ErrorActualizar(f"falló «{' '.join(cmd)[:120]}» (código {r.returncode}); ver {self.registro}")
        return r.returncode


def _validar(p):
    """Fallos de validar-despliegue.sh (su código de salida es el número de fallos)."""
    script = os.path.join(REPO, "deploy/tools/validar-despliegue.sh")
    if not os.path.isfile(script):
        return 0
    return p.orden(["bash", script], obligatoria=False, tiempo=600)


def _url_base_datos():
    for linea in open(os.path.join(REPO, "backend/.env")):
        if linea.startswith("DATABASE_URL="):
            return linea.split("=", 1)[1].strip()
    raise ErrorActualizar("no se encontró DATABASE_URL en backend/.env")


def _respaldo(p):
    destino = os.path.join(RESPALDOS, f"{p.sello}-{p.estado['desde']}")
    os.makedirs(destino, mode=0o700)
    with open(os.path.join(destino, "commit.txt"), "w") as f:
        f.write(p.estado["desde_commit"] + "\n")
    with open(os.path.join(destino, "maildb.dump"), "wb") as f:
        r = subprocess.run(["runuser", "-u", "postgres", "--", "pg_dump", "-Fc", "maildb"], stdout=f,
                           stderr=subprocess.PIPE, timeout=3600, cwd="/tmp")
    if r.returncode != 0:
        raise ErrorActualizar("no se pudo respaldar la base de datos: " + r.stderr.decode(errors="replace")[-200:])
    for viejo in sorted(glob.glob(os.path.join(RESPALDOS, "*")))[:-3]:  # se guardan los 3 últimos
        shutil.rmtree(viejo, ignore_errors=True)
    return destino


def _migraciones(p):
    """Como el usuario de la aplicación (UPGRADING.md); la contraseña va por PGPASSWORD, no en la orden:
    así no queda en el registro ni en la lista de procesos."""
    from urllib.parse import unquote, urlsplit

    url = urlsplit(_url_base_datos())
    entorno = {"PGPASSWORD": unquote(url.password or ""), "PGHOST": url.hostname or "localhost",
               "PGPORT": str(url.port or 5432), "PGUSER": unquote(url.username or ""), "PGDATABASE": url.path.lstrip("/")}
    for archivo in sorted(glob.glob(os.path.join(REPO, "migrations/*.sql"))) + sorted(glob.glob(os.path.join(REPO, "deploy/seeds/*.sql"))):
        p.orden(["psql", "-v", "ON_ERROR_STOP=0", "-q", "-f", archivo], obligatoria=False, entorno=entorno)


def _codigo_y_dependencias(p, commit, desde_commit):
    p.paso("Código")
    git("checkout", "--quiet", "--detach", commit)
    p.paso("Dependencias de Python")
    for entorno in ENTORNOS:
        pip = os.path.join(REPO, entorno, "venv/bin/pip")
        req = os.path.join(REPO, entorno, "requirements.txt")
        if os.path.exists(pip) and os.path.exists(req):
            p.orden([pip, "install", "-q", "--disable-pip-version-check", "-r", req], cwd=os.path.join(REPO, entorno))
    p.paso("Frontend del correo")
    frontend = os.path.join(REPO, "frontend")
    if desde_commit is None or _cambio(desde_commit, commit, "frontend/package-lock.json") or not os.path.isdir(os.path.join(frontend, "node_modules")):
        p.orden(["npm", "ci", "--quiet", "--no-audit", "--no-fund"], cwd=frontend)
    p.orden(["bash", os.path.join(REPO, "deploy-webmail.sh"), "--solo-frontend"])
    p.paso("Frontend del panel")
    panel = os.path.join(REPO, "admin-panel/frontend")
    if os.path.isdir(panel):
        if desde_commit is None or _cambio(desde_commit, commit, "admin-panel/frontend/package-lock.json") or not os.path.isdir(os.path.join(panel, "node_modules")):
            p.orden(["npm", "ci", "--quiet", "--no-audit", "--no-fund"], cwd=panel)
        p.orden(["npx", "vite", "build"], cwd=panel)


def _cambio(desde, hasta, ruta):
    return subprocess.run(["git", "-c", f"safe.directory={REPO}", "-C", REPO, "diff", "--quiet", desde, hasta, "--", ruta],
                          capture_output=True).returncode != 0


def _secciones(p):
    for seccion in SECCIONES:
        if os.path.exists(f"/usr/local/sbin/maquita-{seccion}"):
            p.paso(f"Sección «{seccion}»")
            p.orden(["bash", os.path.join(REPO, "deploy/webmail/instalar-app.sh"), seccion])
    ajustes = os.path.join(REPO, "deploy/ajustes/aplicar-ajustes.sh")
    if os.path.isfile(ajustes):
        p.paso("Ajustes del servidor")
        p.orden(["bash", ajustes, "--aplicar"], obligatoria=False)


def _reiniciar(p):
    p.paso("Reinicio de servicios")
    for servicio in SERVICIOS:
        activo = subprocess.run(["systemctl", "is-enabled", servicio], capture_output=True, text=True).stdout.strip()
        if activo == "enabled":
            p.orden(["systemctl", "restart", servicio], obligatoria=False, tiempo=180)
    p.orden(["nginx", "-t"], obligatoria=False)
    p.orden(["systemctl", "reload", "nginx"], obligatoria=False)
    time.sleep(20)


def instalar(destino):
    """Instala la versión `destino` (ya comprobada por version.objetivo). Corre como root, fuera del panel."""
    try:
        cerrojo = os.open(CERROJO, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ErrorActualizar("ya hay una actualización en curso")
    os.write(cerrojo, str(os.getpid()).encode())
    desde = actual()
    p = Proceso(desde, destino)
    try:
        if desde["cambios_locales"]:
            raise ErrorActualizar("hay cambios locales en el código (" + ", ".join(desde["cambios_locales"][:5]) +
                                  "): no se actualiza para no pisarlos")
        if shutil.disk_usage(REPO).free < 2 * 1024**3:
            raise ErrorActualizar("queda menos de 2 GB libres en el disco")
        p.paso("Validación antes de actualizar")
        fallos_antes = _validar(p)
        p.estado["fallos_antes"] = fallos_antes
        p.paso("Respaldo")
        p.estado["respaldo"] = _respaldo(p)
        _codigo_y_dependencias(p, destino["commit"], desde["commit"])
        p.paso("Migraciones de la base de datos")
        _migraciones(p)
        _secciones(p)
        _reiniciar(p)
        p.paso("Validación después de actualizar")
        fallos = _validar(p)
        p.estado["fallos_despues"] = fallos
        if fallos > fallos_antes:
            raise ErrorActualizar(f"la validación empeoró ({fallos_antes} → {fallos} fallos)")
        p.estado.update(estado="terminada", paso="", fin=time.strftime("%Y-%m-%d %H:%M:%S"), version=actual()["version"])
    except Exception as e:
        p.estado.update(error=str(e)[:500])
        _volver(p, desde)
    finally:
        guardar_json(PROGRESO, p.estado)
        historial = leer_json(HISTORIAL, [])
        historial.insert(0, p.estado)
        guardar_json(HISTORIAL, historial[:30])
        os.close(cerrojo)
        os.remove(CERROJO)
    return p.estado


def _volver(p, desde):
    """Vuelve al código anterior (si se llegó a cambiar) y lo reconstruye."""
    p.anotar(f"\n!! {p.estado.get('error')}")
    if actual()["commit"] == desde["commit"]:
        p.estado.update(estado="fallida", fin=time.strftime("%Y-%m-%d %H:%M:%S"))
        return
    try:
        _codigo_y_dependencias(p, desde["commit"], None)
        _secciones(p)
        _reiniciar(p)
        p.estado.update(estado="revertida", paso="", fin=time.strftime("%Y-%m-%d %H:%M:%S"))
    except Exception as e:
        p.estado.update(estado="fallida", error_vuelta=str(e)[:300], fin=time.strftime("%Y-%m-%d %H:%M:%S"))
