"""Aplicaciones Node.js, Python y estáticas desde el portal (v1.11).

Son las aplicaciones propias del panel general (deploy/sitios/lib/propias.py y propias_servicio.py): el código
corre con el usuario del sitio, encerrado en su unidad de systemd con sus límites (768 MB de memoria, 1,5
núcleos, 256 tareas), solo escucha en 127.0.0.1 y nginx la publica con el cortafuegos de aplicación delante.

Desde el portal, además:
- sin puerto público: abrir puertos del servidor lo hace solo el administrador general;
- el repositorio git, si lo hay, tiene que estar en Internet (red.py);
- crear una aplicación cuenta para el disco del dominio;
- las variables de entorno se reenvían, pero ni sus valores ni sus nombres quedan en el registro del intermediario.
"""

import json
import re

import cuotas
import red
from errores import ErrorPortal
from ordenes_sitios import b64, sitios

TIPOS = ("estatico", "python", "node")
ACCIONES = ("iniciar", "detener", "reiniciar", "desplegar")
CLAVES = {"git": str, "rama": str, "carpeta": str, "spa": bool, "modo": str, "entrada": str}
RE_VARIABLE = re.compile(r"[A-Z_][A-Z0-9_]{0,63}")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
TIEMPO_LARGO = 1150  # dependencias (pip, npm) y arranque


def _conf(ctx):
    conf = ctx.args.get("conf") or {}
    if not isinstance(conf, dict):
        raise ErrorPortal(400, "Configuración no válida")
    if conf.get("puerto_publico") or conf.get("protocolo"):
        raise ErrorPortal(403, "Abrir un puerto del servidor lo hace el administrador general: pídaselo")
    limpia = {}
    for clave, valor in conf.items():
        if clave not in CLAVES or not isinstance(valor, CLAVES[clave]):
            raise ErrorPortal(400, f"Dato no válido: {str(clave)[:40]}")
        if isinstance(valor, str):
            valor = valor.strip()
            if len(valor) > 300 or _CONTROL.search(valor):
                raise ErrorPortal(400, f"Dato no válido: {clave}")
            if not valor:
                continue
        limpia[clave] = valor
    if limpia.get("git"):
        red.repositorio_https(limpia["git"])
    return limpia


def crear(ctx):
    tipo = ctx.args.get("tipo")
    if tipo not in TIPOS:
        raise ErrorPortal(400, "Tipo de aplicación no válido (estática, Python o Node.js)")
    conf = _conf(ctx)
    cuotas.comprobar_disco(ctx.dominio)
    datos = b64(json.dumps(conf, ensure_ascii=False))
    if len(datos) > 8000:
        raise ErrorPortal(400, "Configuración demasiado larga")
    return sitios("propia-crear", ctx.sitio, tipo, datos, tiempo=TIEMPO_LARGO)


def estado(ctx):
    return sitios("propia-estado", ctx.sitio, tiempo=60)


def accion(ctx):
    que = ctx.args.get("accion")
    if que not in ACCIONES:
        raise ErrorPortal(400, "Acción no válida")
    if que == "desplegar":
        cuotas.comprobar_disco(ctx.dominio)
    return sitios("propia-accion", ctx.sitio, que, tiempo=TIEMPO_LARGO)


def entorno(ctx):
    """{"CLAVE": "valor"} pone o cambia, {"CLAVE": null} conserva el valor guardado; las ausentes se quitan."""
    variables = ctx.args.get("variables")
    if not isinstance(variables, dict) or len(variables) > 50:
        raise ErrorPortal(400, "Variables no válidas (máximo 50)")
    for clave, valor in variables.items():
        if not isinstance(clave, str) or not RE_VARIABLE.fullmatch(clave):
            raise ErrorPortal(400, f"Nombre de variable no válido: {str(clave)[:40]} (mayúsculas, números y _)")
        if valor is not None and (not isinstance(valor, str) or len(valor) > 4096 or _CONTROL.search(valor)):
            raise ErrorPortal(400, f"Valor no válido para {clave} (una línea, hasta 4096 caracteres)")
    datos = b64(json.dumps(variables, ensure_ascii=False))
    if len(datos) > 8000:
        raise ErrorPortal(400, "Las variables son demasiado largas en total")
    return sitios("propia-entorno", ctx.sitio, datos, tiempo=300)


def quitar(ctx):
    if str(ctx.args.get("confirmacion") or "").strip().lower() != ctx.sitio:
        raise ErrorPortal(400, "Escriba el nombre del sitio para confirmar")
    return sitios("propia-quitar", ctx.sitio, ctx.sitio, tiempo=300)


ORDENES = {
    "propia-crear": ("sitio", crear),
    "propia-estado": ("sitio", estado),
    "propia-accion": ("sitio", accion),
    "propia-entorno": ("sitio", entorno),
    "propia-quitar": ("sitio", quitar),
}
