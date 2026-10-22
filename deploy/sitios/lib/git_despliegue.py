"""Despliegue desde git de un sitio PHP (v1.11): traer la rama, publicarla y volver a la versión anterior.

Cada despliegue:
  1. corre en segundo plano, en su propia unidad de systemd (sitio-git-<usuario>): ni el panel ni el servidor de
     git esperan, y systemd no deja arrancar dos a la vez para el mismo sitio (además hay un cerrojo);
  2. trae la rama con «git clone --depth 1» a una carpeta nueva de versiones/, CON EL USUARIO DEL SITIO, sin
     ganchos de git, solo por https o ssh y solo desde servidores con dirección pública (red_publica.py);
  3. la publica con rsync, también como el usuario del sitio, hacia la carpeta pública: --delay-updates deja
     todos los archivos nuevos en su sitio al final, casi de golpe, y --delete-delay borra lo que ya no está en
     el repositorio (compara por contenido, --checksum). Las exclusiones (lo que sube la aplicación, la
     verificación de Let's Encrypt e IndexNow) no se copian ni se borran;
  4. se anota (commit, autor, mensaje, duración, salida) y se guardan las últimas VERSIONES_GUARDADAS versiones:
     volver a una es otra pasada de rsync desde su carpeta, sin red.
Antes del PRIMER despliegue se hace una copia del sitio (copias_cliente.py), porque rsync borra lo que hubiera.
"""

import fcntl
import os
import re
import shutil
import subprocess
import time

import git_sitio as gs
import red_publica
from comun import ErrorSitio, ejecutar

MAQUITA_SITIOS = "/usr/local/sbin/maquita-sitios"
CERROJOS = "/run/lock"
VERSIONES_GUARDADAS = 3
SEGUNDOS_ENTRE_GANCHOS = 20
TIEMPO_GIT = 900
TIEMPO_RSYNC = 1200
RE_ID = re.compile(r"\d{8}-\d{6}")
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def unidad(meta):
    return f"sitio-git-{meta['usuario']}"


def en_curso(meta):
    r = subprocess.run(["systemctl", "is-active", unidad(meta)], capture_output=True, text=True, timeout=20)
    return r.stdout.strip() in ("active", "activating", "reloading")


def exclusiones_fijas(meta):
    """Lo que el despliegue nunca toca aunque no esté en la lista del sitio."""
    fijas = [".well-known"]
    if re.fullmatch(r"[0-9a-f]{32}", str(meta.get("indexnow") or "")):
        fijas.append(f"{meta['indexnow']}.txt")
    return fijas


# --- Lanzar en segundo plano ---


def lanzar(dominio, origen):
    """git-desplegar: arranca el despliegue en su unidad y vuelve enseguida."""
    meta = gs.de_sitio(dominio)
    if gs.compatible(meta):
        raise ErrorSitio(f"No se puede desplegar: {gs.compatible(meta)}")
    if en_curso(meta):
        raise ErrorSitio("ya hay un despliegue en curso para este sitio")
    if origen == "gancho":
        ultimo = (meta["git_php"].get("despliegues") or [{}])[-1]
        if time.time() - float(ultimo.get("inicio_ts") or 0) < SEGUNDOS_ENTRE_GANCHOS:
            raise ErrorSitio("demasiados despliegues seguidos: espere unos segundos")
    ejecutar(["systemd-run", "--unit", unidad(meta), "--collect", "--quiet", "--nice=10",
              "--property=RuntimeMaxSec=2400", "--description", f"Despliegue desde git de {dominio}",
              MAQUITA_SITIOS, "git-desplegar-ahora", dominio, origen], tiempo=60)
    return {"dominio": dominio, "en_curso": True, "origen": origen}


class _Cerrojo:
    def __init__(self, dominio):
        self.ruta = os.path.join(CERROJOS, f"maquita-sitios-git-{dominio}.lock")

    def __enter__(self):
        os.makedirs(CERROJOS, exist_ok=True)
        self.fd = os.open(self.ruta, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(self.fd)
            raise ErrorSitio("ya hay un despliegue en curso para este sitio")
        return self

    def __exit__(self, *_):
        fcntl.flock(self.fd, fcntl.LOCK_UN)
        os.close(self.fd)


# --- Órdenes con el usuario del sitio ---


def _entorno_git(meta):
    ssh = (f"ssh -i {gs.ruta_clave(meta)} -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new "
           f"-o UserKnownHostsFile={gs.ruta_conocidos(meta)} -o ConnectTimeout=20")
    return {"HOME": gs.carpeta(meta), "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_ALLOW_PROTOCOL": "https:ssh", "GIT_SSH_COMMAND": ssh}


def _correr(meta, cmd, tiempo, env_extra=None, umask=0o027):
    """Ejecuta `cmd` como el usuario del sitio. Devuelve la salida; si falla, ErrorSitio con su final."""
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": "/tmp", **(env_extra or {})}
    try:
        r = subprocess.run(["runuser", "-u", meta["usuario"], "--", *cmd], capture_output=True, text=True,
                           timeout=tiempo, env=env, cwd="/", umask=umask)
    except subprocess.TimeoutExpired:
        raise ErrorSitio(f"{os.path.basename(cmd[0])} tardó demasiado")
    salida = ((r.stdout or "") + (r.stderr or "")).strip()
    if r.returncode != 0:
        lineas = [x for x in salida.splitlines() if x.strip()]
        raise ErrorSitio(f"{os.path.basename(cmd[0])}: " + (lineas[-1][:300] if lineas else f"código {r.returncode}"))
    return salida


def _traer(meta, git, destino):
    """Clona la rama en `destino` (nuevo) y devuelve {commit, autor, mensaje}."""
    red_publica.comprobar(gs.host_de(git["repo"]))
    env = _entorno_git(meta)
    _correr(meta, ["git", "-c", "core.hooksPath=/dev/null", "-c", "protocol.file.allow=never", "clone", "--quiet",
                   "--depth", "1", "--single-branch", "--no-tags", "--branch", git["rama"], "--", git["repo"], destino],
            TIEMPO_GIT, env)
    linea = _correr(meta, ["git", "-C", destino, "log", "-1", "--format=%H%x1f%an%x1f%s"], 60, env)
    partes = (linea.splitlines()[-1] if linea else "").split("\x1f")
    commit = partes[0] if re.fullmatch(r"[0-9a-f]{40,64}", partes[0] if partes else "") else None
    limpiar = lambda t: _CONTROL.sub(" ", t).strip()[:200]  # noqa: E731
    _correr(meta, ["rm", "-rf", "--", os.path.join(destino, ".git")], 300)
    return {"commit": commit, "autor": limpiar(partes[1]) if len(partes) > 1 else "",
            "mensaje": limpiar(partes[2]) if len(partes) > 2 else ""}


def _origen(version_dir, carpeta):
    origen = os.path.join(version_dir, carpeta) if carpeta else version_dir
    real = os.path.realpath(origen)
    if not (real == os.path.realpath(version_dir) or real.startswith(os.path.realpath(version_dir) + "/")) \
            or not os.path.isdir(real):
        raise ErrorSitio(f"el repositorio no tiene la carpeta «{carpeta}»")
    return origen


def _publicar(meta, git, origen):
    """rsync de `origen` a la carpeta pública como el usuario del sitio (archivos nuevos 0640, carpetas con el
    grupo de nginx heredado de la carpeta pública), sin tocar las exclusiones."""
    excluir = [f"--exclude=/{e}" for e in exclusiones_fijas(meta) + list(git.get("exclusiones") or [])]
    # --checksum: dos versiones con un archivo del mismo tamaño y la misma hora (clonadas en el mismo segundo, o al
    # volver atrás) se distinguen por su contenido, no por la fecha.
    return _correr(meta, ["rsync", "-rlt", "--checksum", "--safe-links", "--delete-delay", "--delay-updates", "--stats", *excluir,
                          "--", origen.rstrip("/") + "/", meta["publico"].rstrip("/") + "/"], TIEMPO_RSYNC)


def _podar(meta, versiones):
    """Deja las VERSIONES_GUARDADAS más recientes y borra las demás carpetas."""
    guardadas, sobran = versiones[-VERSIONES_GUARDADAS:], versiones[:-VERSIONES_GUARDADAS]
    for v in sobran:
        ruta = os.path.join(gs.carpeta_versiones(meta), v["id"])
        if RE_ID.fullmatch(v["id"]) and os.path.lexists(ruta):
            _correr(meta, ["rm", "-rf", "--", ruta], 600)
    return guardadas


def _nuevo_id(meta):
    ident = time.strftime("%Y%m%d-%H%M%S")
    while os.path.lexists(os.path.join(gs.carpeta_versiones(meta), ident)):
        time.sleep(1)
        ident = time.strftime("%Y%m%d-%H%M%S")
    return ident


def _resumen_rsync(salida):
    """Las líneas útiles de --stats (archivos transferidos y borrados)."""
    utiles = [x.strip() for x in salida.splitlines() if x.strip().startswith(("Number of", "Total file size"))]
    return "\n".join(utiles)[-1500:]


# --- Desplegar y volver ---


def desplegar(dominio, origen):
    """git-desplegar-ahora (solo desde la unidad que arranca lanzar)."""
    with _Cerrojo(dominio):
        meta = gs.de_sitio(dominio)
        git = meta["git_php"]
        ident = _nuevo_id(meta)
        inicio = time.time()
        registro = {"id": ident, "inicio": time.strftime("%Y-%m-%d %H:%M:%S"), "inicio_ts": int(inicio),
                    "origen": origen, "estado": "en curso"}
        gs.anotar(dominio, lambda g: g.setdefault("despliegues", []).append(registro))
        temporal = os.path.join(gs.carpeta_versiones(meta), f".nueva-{ident}")
        try:
            if gs.compatible(meta):
                raise ErrorSitio(gs.compatible(meta))
            if not git.get("versiones"):
                import copias_cliente

                try:
                    copias_cliente.crear(dominio, "antes del primer despliegue desde git")
                except ErrorSitio as e:
                    raise ErrorSitio(f"no se pudo hacer la copia del sitio antes del primer despliegue ({e})")
            gs._preparar(meta)
            datos = _traer(meta, git, temporal)
            final = os.path.join(gs.carpeta_versiones(meta), ident)
            os.rename(temporal, final)
            salida = _publicar(meta, git, _origen(final, git.get("carpeta", "")))
        except Exception as e:
            if os.path.lexists(temporal):
                try:
                    _correr(meta, ["rm", "-rf", "--", temporal], 600)
                except ErrorSitio:
                    pass
            texto = str(e) if isinstance(e, ErrorSitio) else f"fallo interno: {type(e).__name__}"
            _cerrar(dominio, ident, inicio, estado="error", error=texto[:400])
            raise
        version = {"id": ident, "commit": datos["commit"], "carpeta": git.get("carpeta", ""),
                   "fecha": registro["inicio"], "mensaje": datos["mensaje"][:120]}

        def poner(g):
            g["versiones"] = _podar(meta, list(g.get("versiones") or []) + [version])
            g["actual"] = ident

        gs.anotar(dominio, poner)
        _cerrar(dominio, ident, inicio, estado="ok", salida=_resumen_rsync(salida), **datos)
        return gs.estado(dominio)


def volver(dominio, ident):
    """git-volver: publica otra vez una versión guardada (la anterior u otra de las que quedan)."""
    if not isinstance(ident, str) or not RE_ID.fullmatch(ident):
        raise ErrorSitio("versión no válida")
    with _Cerrojo(dominio):
        meta = gs.de_sitio(dominio)
        git = meta["git_php"]
        version = next((v for v in git.get("versiones") or [] if v.get("id") == ident), None)
        if not version:
            raise ErrorSitio("esa versión ya no está guardada")
        if ident == git.get("actual"):
            raise ErrorSitio("esa es la versión publicada ahora")
        carpeta = os.path.join(gs.carpeta_versiones(meta), ident)
        if os.path.islink(carpeta) or not os.path.isdir(carpeta):
            raise ErrorSitio("la carpeta de esa versión ya no está")
        inicio = time.time()
        registro = {"id": time.strftime("%Y%m%d-%H%M%S"), "inicio": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "inicio_ts": int(inicio), "origen": "volver", "estado": "en curso", "version": ident}
        gs.anotar(dominio, lambda g: g.setdefault("despliegues", []).append(registro))
        try:
            salida = _publicar(meta, git, _origen(carpeta, version.get("carpeta", "")))
        except ErrorSitio as e:
            _cerrar(dominio, registro["id"], inicio, estado="error", error=str(e)[:400])
            raise
        gs.anotar(dominio, lambda g: g.update(actual=ident))
        _cerrar(dominio, registro["id"], inicio, estado="ok", salida=_resumen_rsync(salida), commit=version.get("commit"),
                mensaje=f"vuelta a la versión {ident}")
        return gs.estado(dominio)


def _cerrar(dominio, ident, inicio, **datos):
    def cambio(g):
        for r in reversed(g.get("despliegues") or []):
            if r.get("id") == ident:
                r.update({k: v for k, v in datos.items() if v not in (None, "")},
                         fin=time.strftime("%Y-%m-%d %H:%M:%S"), segundos=round(time.time() - inicio))
                break

    try:
        gs.anotar(dominio, cambio)
    except ErrorSitio:
        pass  # la configuración se quitó mientras tanto: no hay dónde anotarlo


def limpiar_para_baja(meta):
    """Al dar de baja el sitio: el gancho se borra (la carpeta de despliegues va a la papelera con el sitio)."""
    ruta = gs.ruta_gancho(meta["dominio"])
    if os.path.exists(ruta):
        os.remove(ruta)


def herramientas():
    """¿Están git, rsync y ssh-keygen? (el ajuste 69 los instala)."""
    return {h: bool(shutil.which(h)) for h in ("git", "rsync", "ssh-keygen", "systemd-run")}
