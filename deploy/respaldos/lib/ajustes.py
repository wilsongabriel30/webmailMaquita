"""Configuración y utilidades de los respaldos del servidor (restic).

Un repositorio restic LOCAL (/var/backups/maquita-respaldos/repo: restauraciones rápidas y protección frente a
errores) y, opcional, un DESTINO EXTERNO al que se copia cada respaldo (otro servidor por SFTP, un servidor
REST de restic, un almacenamiento S3 o una carpeta montada, p. ej. un disco USB): lo que protege frente a la
pérdida del disco o del servidor. Los dos se cifran con la misma clave de recuperación, que vive en
/etc/maquita-respaldos/clave y que hay que guardar FUERA del servidor: sin ella los respaldos no se abren.
"""

import json
import os
import re
import subprocess

DIR_CONF = "/etc/maquita-respaldos"
CONFIG = os.path.join(DIR_CONF, "config.json")
CLAVE = os.path.join(DIR_CONF, "clave")
SECRETOS_DESTINO = os.path.join(DIR_CONF, "destino.env")
CLAVE_SSH = os.path.join(DIR_CONF, "id_ed25519")
BASE = "/var/backups/maquita-respaldos"
REPO_LOCAL = os.path.join(BASE, "repo")
VOLCADOS = os.path.join(BASE, "volcados")
ESTADO = "/var/lib/maquita-respaldos/estado.json"
REGISTROS = "/var/log/maquita-respaldos"
CERROJO = "/run/maquita-respaldos.lock"
APP = "/opt/maquita-webmail"

# Qué se respalda. /etc se respalda entero (configuración, certificados, claves, zonas, sitios, cortafuegos);
# al restaurar el servidor solo se devuelve una lista acotada (ver restaurar.py).
RUTAS = ["/etc", "/var/vmail", "/var/lib/radicale", "/var/lib/maquita-almacen", "/var/lib/rspamd/dkim", "/srv/sitios",
         "/var/lib/maquita-actualizar", APP, VOLCADOS, "/root/LEEME-primer-arranque.txt"]
EXCLUIR = ["node_modules", "venv", "__pycache__", "*.pyc", f"{APP}/frontend/dist", f"{APP}/admin-panel/frontend/dist",
           f"{APP}/deploy-backups", f"{APP}/.git", "/etc/maquita-respaldos/clave", "/srv/sitios/*/tmp/.cache-pip",
           "/srv/sitios/*/tmp/.npm", "/srv/sitios/*/entorno"]
TIPOS_DESTINO = ("ninguno", "sftp", "rest", "s3", "carpeta")
RE_VARIABLE = re.compile(r"^[A-Z][A-Z0-9_]{1,40}$")


class ErrorRespaldo(Exception):
    pass


def leer_json(ruta, defecto):
    try:
        with open(ruta) as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return defecto


def guardar_json(ruta, datos, modo=0o600):
    os.makedirs(os.path.dirname(ruta), mode=0o700, exist_ok=True)
    tmp = ruta + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, modo), "w") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)
    os.replace(tmp, ruta)


def config():
    conf = {"automatico": True, "conservar": {"diarios": 7, "semanales": 4, "mensuales": 6},
            "destino": {"tipo": "ninguno", "url": ""}}
    conf.update(leer_json(CONFIG, {}))
    return conf


def validar_config(datos):
    if not isinstance(datos, dict):
        raise ErrorRespaldo("configuración no válida")
    conservar = datos.get("conservar") or {}
    limpio = {"automatico": bool(datos.get("automatico", True)), "conservar": {}}
    for clave, (minimo, maximo) in {"diarios": (1, 60), "semanales": (0, 52), "mensuales": (0, 60)}.items():
        try:
            valor = int(conservar.get(clave, 7 if clave == "diarios" else 4 if clave == "semanales" else 6))
        except (TypeError, ValueError):
            raise ErrorRespaldo(f"«{clave}» no válido")
        if not minimo <= valor <= maximo:
            raise ErrorRespaldo(f"«{clave}» debe estar entre {minimo} y {maximo}")
        limpio["conservar"][clave] = valor
    destino = datos.get("destino") or {}
    tipo = destino.get("tipo", "ninguno")
    url = str(destino.get("url", "")).strip()
    if tipo not in TIPOS_DESTINO:
        raise ErrorRespaldo("tipo de destino no válido")
    if tipo != "ninguno":
        patrones = {"sftp": r"^sftp:[A-Za-z0-9._-]+@[A-Za-z0-9.-]+(:\d{1,5})?:/[A-Za-z0-9._/-]{1,200}$",
                    "rest": r"^rest:https://[A-Za-z0-9.:-]+(/[A-Za-z0-9._/-]*)?$",
                    "s3": r"^s3:https://[A-Za-z0-9.:-]+/[A-Za-z0-9._/-]{1,200}$",
                    "carpeta": r"^/[A-Za-z0-9._/-]{1,200}$"}
        if not re.match(patrones[tipo], url) or ".." in url:
            raise ErrorRespaldo({"sftp": "SFTP: sftp:usuario@servidor:/ruta",
                                 "rest": "REST: rest:https://servidor:8000/ruta",
                                 "s3": "S3: s3:https://servidor/cubo/ruta",
                                 "carpeta": "Carpeta: ruta absoluta montada (p. ej. /mnt/usb/respaldos)"}[tipo])
        if tipo == "carpeta" and (url.startswith(BASE) or not os.path.isdir(os.path.dirname(url.rstrip("/")) or "/")):
            raise ErrorRespaldo("la carpeta debe estar en otro disco montado, fuera de los respaldos locales")
    limpio["destino"] = {"tipo": tipo, "url": url if tipo != "ninguno" else ""}
    return limpio


def guardar_secretos_destino(secretos):
    """Credenciales del destino externo (S3: AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY; REST: usuario y clave en
    RESTIC_REST_USERNAME/RESTIC_REST_PASSWORD). Solo root las lee; nunca vuelven al panel."""
    if not isinstance(secretos, dict) or len(secretos) > 10:
        raise ErrorRespaldo("credenciales no válidas")
    lineas = []
    for clave, valor in secretos.items():
        if clave not in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION", "RESTIC_REST_USERNAME",
                         "RESTIC_REST_PASSWORD") or not isinstance(valor, str) or re.search(r"[\x00-\x1f\x7f]", valor) \
                or len(valor) > 300:
            raise ErrorRespaldo(f"credencial no válida: {str(clave)[:40]}")
        lineas.append(f"{clave}={valor}")
    os.makedirs(DIR_CONF, mode=0o700, exist_ok=True)
    with open(os.open(SECRETOS_DESTINO, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
        f.write("\n".join(lineas) + ("\n" if lineas else ""))


def entorno_restic():
    env = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8", "HOME": "/root",
           "RESTIC_PASSWORD_FILE": CLAVE, "RESTIC_CACHE_DIR": "/var/cache/maquita-respaldos"}
    try:
        with open(SECRETOS_DESTINO) as f:
            for linea in f:
                clave, _, valor = linea.rstrip("\n").partition("=")
                if RE_VARIABLE.match(clave):
                    env[clave] = valor
    except FileNotFoundError:
        pass
    return env


def restic(repo, *args, tiempo=6 * 3600, registro=None, json_salida=False):
    """restic contra un repositorio. Con json_salida devuelve los datos; si no, el texto."""
    orden = ["restic", "--repo", repo, *args] + (["--json"] if json_salida else [])
    if repo.startswith("sftp:"):
        # Clave SSH propia de los respaldos (su parte pública se autoriza en el servidor de destino).
        orden[3:3] = ["-o", f"sftp.args=-i {CLAVE_SSH} -o StrictHostKeyChecking=accept-new -o BatchMode=yes"]
    if registro:
        with open(registro, "a") as f:
            f.write("$ " + " ".join(orden) + "\n")
    r = subprocess.run(orden, capture_output=True, text=True, timeout=tiempo, env=entorno_restic())
    if registro:
        with open(registro, "a") as f:
            f.write((r.stdout if not json_salida else "")[-20000:] + r.stderr[-5000:])
    if r.returncode != 0:
        detalle = (r.stderr or r.stdout).strip().splitlines()
        raise ErrorRespaldo("restic: " + (detalle[-1][:300] if detalle else f"código {r.returncode}"))
    if json_salida:
        texto = r.stdout.strip()
        try:
            return json.loads(texto)
        except ValueError:
            # «backup --json» emite una línea por evento: la última es el resumen.
            return json.loads(texto.splitlines()[-1]) if texto else None
    return r.stdout


def repo_externo(conf=None):
    destino = (conf or config())["destino"]
    return destino["url"] if destino["tipo"] != "ninguno" else None


def iniciar_repo(repo, desde_local=False):
    """Crea el repositorio si no existe. El externo se crea con los mismos parámetros de troceado que el local
    (así «restic copy» no vuelve a subir lo que ya está)."""
    try:
        restic(repo, "cat", "config", tiempo=120)
        return False
    except ErrorRespaldo:
        pass
    if desde_local:
        restic(repo, "init", "--from-repo", REPO_LOCAL, "--from-password-file", CLAVE, "--copy-chunker-params", tiempo=300)
    else:
        os.makedirs(os.path.dirname(repo), mode=0o700, exist_ok=True)
        restic(repo, "init", tiempo=300)
    return True
