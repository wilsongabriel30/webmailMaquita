"""Despliegue desde git de un sitio PHP (v1.11): configuración, clave de despliegue y gancho.

Es para los sitios PHP propios (vacíos o con un paquete subido), no para las aplicaciones del catálogo
(WordPress, Joomla…: tienen sus propias actualizaciones) ni para las aplicaciones propias Python/Node, que ya se
despliegan desde git por su lado (propias.py).

En el meta del sitio («git_php»): repositorio, rama, carpeta del repositorio que se publica, carpeta que sirve la
web, archivos que el despliegue nunca toca (lo subido por la aplicación), si hay gancho, y el registro y las
versiones de los despliegues. En disco, todo del usuario del sitio y fuera de la carpeta pública:

    /srv/sitios/<dominio>/despliegues/            <usuario> 0700 (PHP no llega: open_basedir)
    /srv/sitios/<dominio>/despliegues/.ssh/       clave de despliegue (ed25519) y servidores conocidos
    /srv/sitios/<dominio>/despliegues/.credencial/ token o contraseña, si se eligió ese método (git_clave.py)
    /srv/sitios/<dominio>/despliegues/versiones/  las últimas versiones desplegadas, para volver atrás

La clave privada la puede leer el usuario del sitio (es la de su repositorio): por eso se pide añadirla en el
servidor de git como clave de SOLO LECTURA. Otras formas de autenticarse (clave propia, token, usuario y contraseña)
se eligen en «Autenticación» (git_credencial.py). El secreto del gancho no: lo guarda root en GANCHOS, y lo comprueba
el intermediario del portal (deploy/sitios/portal/lib/publico.py), que recibe las llamadas del servidor de git.
"""

import json
import os
import re
import secrets
import time

import git_clave as gc
import red_publica
from comun import ErrorSitio, ejecutar, guardar_meta, leer_meta

GANCHOS = "/etc/maquita-sitios/ganchos"
RUTA_GANCHO = "/git-despliegue/"  # dirección pública: https://<servidor>/git-despliegue/<sitio>

RE_RAMA = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,99}")
RE_CARPETA = re.compile(r"[A-Za-z0-9._-]{1,60}(?:/[A-Za-z0-9._-]{1,60}){0,5}")
MAX_EXCLUSIONES = 20
MAX_REGISTRO = 10
# Apps con las que convive el despliegue desde git: ninguna (sitio vacío) o un paquete propio.
COMPATIBLES = (None, "paquete")


# Carpetas, clave y autenticación: comunes con las aplicaciones propias (git_clave.py).
carpeta, carpeta_ssh, ruta_clave, ruta_conocidos = gc.carpeta, gc.carpeta_ssh, gc.ruta_clave, gc.ruta_conocidos
host_de, clave_publica, RE_CLAVE_PUBLICA = gc.host_de, gc.clave_publica, gc.RE_CLAVE_PUBLICA


def carpeta_versiones(meta):
    return os.path.join(carpeta(meta), "versiones")


def ruta_gancho(dominio):
    return os.path.join(GANCHOS, f"{dominio}.json")


# --- Validación ---


def _rama(valor):
    rama = (valor or "main").strip() if isinstance(valor, (str, type(None))) else None
    if not rama or not RE_RAMA.fullmatch(rama) or ".." in rama or rama.endswith(("/", ".lock")) or "//" in rama:
        raise ErrorSitio("rama no válida")
    return rama


def _carpeta_relativa(valor, que):
    """Carpeta relativa («» = la raíz), sin «..» ni «.»; las barras de los extremos se quitan."""
    if valor in (None, ""):
        return ""
    if not isinstance(valor, str):
        raise ErrorSitio(f"{que} no válida")
    limpio = valor.strip().strip("/")
    if not limpio:
        return ""
    if not RE_CARPETA.fullmatch(limpio) or any(p in (".", "..") for p in limpio.split("/")):
        raise ErrorSitio(f"{que} no válida: letras, números, . _ - y barras, sin «..»")
    return limpio


def validar(datos):
    """Configuración limpia {repo, rama, carpeta, raiz_web, exclusiones} o ErrorSitio."""
    if not isinstance(datos, dict) or set(datos) - {"repo", "rama", "carpeta", "raiz_web", "exclusiones"}:
        raise ErrorSitio("configuración no válida")
    repo = str(datos.get("repo") or "").strip()
    red_publica.comprobar(host_de(repo))
    exclusiones = datos.get("exclusiones") or []
    if not isinstance(exclusiones, list) or len(exclusiones) > MAX_EXCLUSIONES:
        raise ErrorSitio(f"se admiten hasta {MAX_EXCLUSIONES} archivos o carpetas que el despliegue no toca")
    limpias = []
    for e in exclusiones:
        c = _carpeta_relativa(e, "Ruta que no se toca")
        if c and c not in limpias:
            limpias.append(c)
    return {"repo": repo, "rama": _rama(datos.get("rama")),
            "carpeta": _carpeta_relativa(datos.get("carpeta"), "Carpeta del repositorio"),
            "raiz_web": _carpeta_relativa(datos.get("raiz_web"), "Carpeta que sirve la web"), "exclusiones": limpias}


# --- Carpetas y clave (todo con el usuario del sitio) ---


def _preparar(meta):
    """despliegues/ (con .ssh/ y .credencial/) y versiones/, del usuario del sitio."""
    gc.preparar(meta)
    ejecutar(["mkdir", "-p", "-m", "700", carpeta_versiones(meta)], como=meta["usuario"])


def generar_clave(meta):
    """Clave ed25519 nueva (la anterior deja de valer en cuanto se borre del servidor de git)."""
    _preparar(meta)
    gc.generar_clave(meta)


# --- Meta ---


def de_sitio(dominio):
    meta = leer_meta(dominio)
    if not meta.get("git_php"):
        raise ErrorSitio("el sitio no tiene configurado el despliegue desde git")
    return meta


def compatible(meta):
    """None si el sitio admite el despliegue desde git; si no, el motivo."""
    if meta.get("app") == "propia":
        return "es una aplicación propia (Python, Node o estática): se despliega desde su pestaña"
    if meta.get("app") not in COMPATIBLES:
        return f"tiene {meta.get('app')} del catálogo, que se actualiza por su cuenta: use un sitio vacío"
    return None


def anotar(dominio, cambio):
    """Aplica `cambio(git_php)` sobre el meta recién leído y lo guarda (otra orden pudo cambiar el meta entretanto)."""
    meta = leer_meta(dominio)
    if not meta.get("git_php"):
        raise ErrorSitio("el despliegue desde git se quitó mientras tanto")
    cambio(meta["git_php"])
    meta["git_php"]["despliegues"] = meta["git_php"].get("despliegues", [])[-MAX_REGISTRO:]
    guardar_meta(meta)
    return meta


def _aplicar_raiz(meta, raiz_web):
    """El sitio pasa a «paquete» (reglas comunes y el perfil general del cortafuegos) con su carpeta web."""
    import sitio

    anterior = (meta.get("app"), json.dumps(meta.get("paquete")))
    paquete = dict(meta.get("paquete") or {})
    paquete.update({"raiz": raiz_web, "origen": "git"})
    if (meta.get("app"), json.dumps(paquete)) == anterior:
        return
    meta["app"], meta["paquete"] = "paquete", paquete
    meta.setdefault("app_admin", ("https://" if meta.get("ssl") else "http://") + meta["dominio"] + "/")
    sitio.publicar_vhost(meta)  # si nginx lo rechaza, deja el vhost anterior y lanza ErrorSitio


def configurar(dominio, datos):
    meta = leer_meta(dominio)
    motivo = compatible(meta)
    if motivo:
        raise ErrorSitio(f"El despliegue desde git no está disponible para este sitio: {motivo}")
    conf = validar(datos)
    nuevo = not meta.get("git_php")
    if nuevo and os.path.exists(ruta_gancho(dominio)):
        os.remove(ruta_gancho(dominio))  # de un sitio anterior con el mismo nombre
    respaldo = {k: meta.get(k) for k in ("app", "paquete", "git_php", "app_admin")}
    git = dict(meta.get("git_php") or {}, **conf)
    git.setdefault("gancho", False)
    git.setdefault("despliegues", [])
    git.setdefault("versiones", [])
    meta["git_php"] = git
    try:
        metodo = gc.metodo(meta, "clave-generada")
        gc.comprobar_metodo(metodo, gc.validar_repo(conf["repo"])[0])
        if metodo == "clave-generada" and not clave_publica(meta):
            generar_clave(meta)
            meta["git_auth"] = gc.registro_generada(meta)
        elif (respaldo.get("git_php") or {}).get("repo") != conf["repo"]:
            # Otro repositorio (quizá otro servidor de git): su huella se aprende de nuevo en el próximo despliegue.
            ejecutar(["rm", "-f", "--", ruta_conocidos(meta)], como=meta["usuario"])
        _aplicar_raiz(meta, conf["raiz_web"])
    except ErrorSitio:
        for k, v in respaldo.items():
            if v is None:
                meta.pop(k, None)
            else:
                meta[k] = v
        guardar_meta(meta)
        raise
    guardar_meta(meta)
    return estado(dominio)


def regenerar_clave(dominio):
    meta = de_sitio(dominio)
    generar_clave(meta)
    meta = leer_meta(dominio)
    meta["git_auth"] = gc.registro_generada(meta)
    guardar_meta(meta)
    return estado(dominio)


def gancho(dominio, accion):
    """activar: secreto nuevo (se devuelve UNA vez); desactivar: lo borra."""
    meta = de_sitio(dominio)
    ruta = ruta_gancho(dominio)
    if accion == "desactivar":
        if os.path.exists(ruta):
            os.remove(ruta)
        anotar(dominio, lambda g: g.update(gancho=False))
        return estado(dominio)
    secreto = secrets.token_urlsafe(32)
    os.makedirs(GANCHOS, mode=0o700, exist_ok=True)
    tmp = ruta + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600), "w") as f:
        json.dump({"dominio": dominio, "secreto": secreto, "creado": time.strftime("%Y-%m-%d %H:%M")}, f)
    os.replace(tmp, ruta)
    anotar(dominio, lambda g: g.update(gancho=True))
    return dict(estado(dominio), secreto=secreto, gancho_ruta=RUTA_GANCHO + meta["dominio"])


def quitar(dominio):
    """Quita la configuración, la clave, las versiones guardadas y el gancho. Los archivos publicados se quedan."""
    meta = de_sitio(dominio)
    if os.path.exists(ruta_gancho(dominio)):
        os.remove(ruta_gancho(dominio))
    if os.path.isdir(carpeta(meta)) and not os.path.islink(carpeta(meta)):
        ejecutar(["rm", "-rf", "--", carpeta(meta)], como=meta["usuario"], tiempo=600)
        if os.path.isdir(carpeta(meta)):
            os.rmdir(carpeta(meta))
    meta.pop("git_php", None)
    meta.pop("git_auth", None)  # la clave o la credencial se fueron con la carpeta de despliegues
    if isinstance(meta.get("paquete"), dict):
        meta["paquete"].pop("origen", None)
    guardar_meta(meta)
    return {"dominio": dominio, "configurado": False, "quitado": True}


def estado(dominio):
    import git_despliegue

    meta = leer_meta(dominio)
    motivo = compatible(meta)
    git = meta.get("git_php")
    if not git:
        return {"dominio": dominio, "configurado": False, "compatible": motivo is None, "motivo": motivo}
    return {
        "dominio": dominio, "configurado": True, "compatible": motivo is None, "motivo": motivo,
        **{k: git.get(k) for k in ("repo", "rama", "carpeta", "raiz_web", "exclusiones", "actual")},
        "gancho": bool(git.get("gancho")) and os.path.exists(ruta_gancho(dominio)),
        "gancho_ruta": RUTA_GANCHO + dominio,
        "clave_publica": clave_publica(meta),
        "en_curso": git_despliegue.en_curso(meta),
        "versiones": git.get("versiones", []),
        "despliegues": list(reversed(git.get("despliegues", []))),
        "exclusiones_fijas": git_despliegue.exclusiones_fijas(meta),
    }
