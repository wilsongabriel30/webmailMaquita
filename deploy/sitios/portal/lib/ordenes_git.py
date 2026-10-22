"""Despliegue desde git de los sitios PHP, desde el portal (v1.11).

Cada orden es la de maquita-sitios del mismo nombre (deploy/sitios/lib/git_sitio.py y git_despliegue.py). Aquí se
comprueba la forma de lo que llega y la cuota de disco antes de desplegar; maquita-sitios vuelve a validarlo todo
(también que el servidor de git esté en Internet). El secreto del gancho vuelve una sola vez, al activarlo, y no
pasa por ningún registro. El gancho en sí (las llamadas del servidor de git) lo atiende publico.py.
"""

import json
import re

import cuotas
from errores import ErrorPortal
from ordenes_sitios import b64, sitios

CLAVES = ("repo", "rama", "carpeta", "raiz_web", "exclusiones")
RE_VERSION = re.compile(r"\d{8}-\d{6}")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def _texto(valor, que, maximo=400):
    if valor is None:
        return ""
    if not isinstance(valor, str) or len(valor) > maximo or _CONTROL.search(valor):
        raise ErrorPortal(400, f"{que} no válido")
    return valor.strip()


def estado(ctx):
    return sitios("git-estado", ctx.sitio, tiempo=60)


def configurar(ctx):
    datos = ctx.args.get("git")
    if not isinstance(datos, dict) or set(datos) - set(CLAVES):
        raise ErrorPortal(400, "Configuración no válida")
    exclusiones = datos.get("exclusiones") or []
    if not isinstance(exclusiones, list) or len(exclusiones) > 20:
        raise ErrorPortal(400, "Se admiten hasta 20 archivos o carpetas que el despliegue no toca")
    limpio = {"repo": _texto(datos.get("repo"), "Repositorio"), "rama": _texto(datos.get("rama"), "Rama", 100) or "main",
              "carpeta": _texto(datos.get("carpeta"), "Carpeta", 300),
              "raiz_web": _texto(datos.get("raiz_web"), "Carpeta web", 300),
              "exclusiones": [_texto(e, "Ruta", 300) for e in exclusiones]}
    if not limpio["repo"]:
        raise ErrorPortal(400, "Falta el repositorio")
    texto = b64(json.dumps(limpio, ensure_ascii=False))
    if len(texto) > 8000:
        raise ErrorPortal(400, "Configuración demasiado larga")
    return sitios("git-configurar", ctx.sitio, texto, tiempo=120)


def clave(ctx):
    return sitios("git-clave", ctx.sitio, tiempo=60)


def gancho(ctx):
    accion = ctx.args.get("accion")
    if accion not in ("activar", "desactivar"):
        raise ErrorPortal(400, "Acción no válida")
    return sitios("git-gancho", ctx.sitio, accion, tiempo=60)


def desplegar(ctx):
    cuotas.comprobar_disco(ctx.dominio)
    return sitios("git-desplegar", ctx.sitio, "panel", tiempo=60)


def volver(ctx):
    version = ctx.args.get("version")
    if not isinstance(version, str) or not RE_VERSION.fullmatch(version):
        raise ErrorPortal(400, "Versión no válida")
    return sitios("git-volver", ctx.sitio, version, tiempo=1190)


def quitar(ctx):
    if str(ctx.args.get("confirmacion") or "").strip().lower() != ctx.sitio:
        raise ErrorPortal(400, "Escriba el nombre del sitio para confirmar")
    return sitios("git-quitar", ctx.sitio, ctx.sitio, tiempo=300)


ORDENES = {
    "git-estado": ("sitio", estado),
    "git-configurar": ("sitio", configurar),
    "git-clave": ("sitio", clave),
    "git-gancho": ("sitio", gancho),
    "git-desplegar": ("sitio", desplegar),
    "git-volver": ("sitio", volver),
    "git-quitar": ("sitio", quitar),
}
