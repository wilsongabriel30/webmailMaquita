"""Órdenes de sitios web: cada una se traduce a UNA llamada a maquita-sitios con argumentos fijos.

Cada función recibe el contexto ya comprobado (administrador, sitio dentro de su alcance y dominio
asignado del que cuelga) y solo toma de `args` lo que su orden necesita, con su forma exacta.
Lo que no se ofrece al portal no tiene función: no hay forma de pedirlo.
"""

import base64
import json
import os
import re

import alcance
import ayudantes
import cuotas
import rutas
import sesion
from errores import ErrorPortal

RE_CORREO = re.compile(r"^[a-z0-9][a-z0-9._+-]{0,63}@([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
RE_TAREA = re.compile(r"^[0-9a-f]{8}$")
RE_BASE = re.compile(r"^[wx]_[a-z0-9]+(_[0-9a-f]{4})?$")
RE_VERSION_PHP = re.compile(r"^[578]\.[0-9]$")
RE_VERSION_GUARDADA = re.compile(r"^\d{8}-\d{6}-\d{3}$")


def b64(texto):
    return base64.urlsafe_b64encode(texto.encode()).decode().rstrip("=")


def sitios(*args, tiempo=300):
    return ayudantes.ejecutar("maquita-sitios", list(args), tiempo=tiempo)


def _texto(ctx, nombre, maximo=200):
    valor = ctx.args.get(nombre)
    if not isinstance(valor, str) or not valor.strip() or len(valor) > maximo:
        raise ErrorPortal(400, f"Falta o no es válido: {nombre}")
    return valor.strip()


def _correo(ctx):
    """Un correo válido de sus dominios o de fuera; nunca de otro dominio de este servidor."""
    correo = _texto(ctx, "correo", 254).lower()
    if not RE_CORREO.fullmatch(correo):
        raise ErrorPortal(400, "Correo no válido")
    dominio = correo.split("@", 1)[1]
    propio = any(alcance.en_alcance(dominio, d) for d in ctx.admin["dominios"])
    if not propio and dominio in sesion.dominios_del_servidor():
        raise ErrorPortal(400, "Use un correo de sus dominios o una dirección de fuera de este servidor")
    return correo


# --- Lista, catálogo y alta ---


def listar(ctx):
    dominios = ctx.admin["dominios"]
    todos = sitios("listar", tiempo=180).get("sitios", [])
    propios = [s for s in todos if any(alcance.en_alcance(s.get("dominio", ""), d) for d in dominios)]
    guardadas = sesion.cuotas_guardadas(dominios)
    por_dominio = []
    for d in dominios:
        suyos = [s for s in propios if alcance.en_alcance(s["dominio"], d)]
        disco = sum(float(s.get("ocupado_mb") or 0) for s in suyos) + cuotas.copias_bytes([s["dominio"] for s in suyos]) / cuotas.MB
        uso = {"sitios": len(suyos), "disco_mb": round(disco, 1),
               "bases_mb": cuotas.bases_mb([s["dominio"] for s in suyos])}
        por_dominio.append({"dominio": d, "cuota": cuotas.de(d, guardadas), "uso": uso})
    return {"sitios": propios, "dominios": por_dominio, "dns": os.path.isfile(rutas.MAQUITA_DNS)}


def catalogo(ctx):
    return sitios("catalogo")


def crear(ctx):
    if alcance.sitio_existe(ctx.sitio):
        raise ErrorPortal(409, f"El sitio {ctx.sitio} ya existe")
    if alcance.es_alias(ctx.sitio):
        raise ErrorPortal(403, f"{ctx.sitio} está reservado: lo usa otro sitio de este servidor")
    cuotas.comprobar_sitios(ctx.dominio)
    return sitios("crear", ctx.sitio, "con-www" if ctx.args.get("www", True) else "sin-www")


def app(ctx):
    aplicacion = _texto(ctx, "aplicacion", 30)
    titulo = _texto(ctx, "titulo", 100)
    if len(b64(titulo)) > 200:
        raise ErrorPortal(400, "El título es demasiado largo")
    correo = _correo(ctx)
    cuotas.comprobar_disco(ctx.dominio)
    return sitios("app", ctx.sitio, aplicacion, b64(titulo), correo, tiempo=1200)


# --- Acceso, HTTPS y mantenimiento de la aplicación ---


def simple(orden, tiempo=300):
    def funcion(ctx):
        return sitios(orden, ctx.sitio, tiempo=tiempo)

    funcion.__name__ = orden.replace("-", "_")
    return funcion


def ssl(ctx):
    return sitios("ssl", ctx.sitio, _correo(ctx), tiempo=360)


def ftp(ctx):
    accion = ctx.args.get("accion")
    if accion not in ("activar", "desactivar"):
        raise ErrorPortal(400, "Acción no válida")
    return sitios("ftp", ctx.sitio, accion)


# --- Tareas programadas (se ejecutan con el usuario del sitio, encerradas en su carpeta) ---


def tareas_guardar(ctx):
    lista = ctx.args.get("lista")
    if not isinstance(lista, list) or len(lista) > 20:
        raise ErrorPortal(400, "Se admiten hasta 20 trabajos por sitio")
    datos = b64(json.dumps(lista, ensure_ascii=False))
    if len(datos) > 40000:
        raise ErrorPortal(400, "La lista de trabajos es demasiado larga")
    return sitios("tareas-guardar", ctx.sitio, datos)


def tarea(orden):
    def funcion(ctx):
        tarea = ctx.args.get("id")
        if not isinstance(tarea, str) or not RE_TAREA.fullmatch(tarea):
            raise ErrorPortal(400, "Trabajo no válido")
        return sitios(orden, ctx.sitio, tarea)

    return funcion


# --- Bases de datos ---


def base_crear(ctx):
    motor = ctx.args.get("motor")
    if motor not in ("mariadb", "postgresql"):
        raise ErrorPortal(400, "Motor no válido")
    cuotas.comprobar_bases(ctx.dominio)
    return sitios("base-crear", ctx.sitio, motor)


def _base(ctx, patron=RE_BASE):
    base = ctx.args.get("base")
    if not isinstance(base, str) or not patron.fullmatch(base):
        raise ErrorPortal(400, "Base de datos no válida")
    return base


def base_entrar(ctx):
    herramienta = ctx.args.get("herramienta")
    if herramienta not in ("phpmyadmin", "adminer"):
        raise ErrorPortal(400, "Herramienta no válida")
    return sitios("base-entrar", ctx.sitio, _base(ctx), herramienta)


def base_borrar(ctx):
    return sitios("base-borrar", ctx.sitio, _base(ctx, re.compile(r"^x_[a-z0-9]+_[0-9a-f]{4}$")))
