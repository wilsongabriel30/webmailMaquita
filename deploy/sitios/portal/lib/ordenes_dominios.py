"""Alias de dominio de un sitio desde el portal (v1.11): otros nombres que muestran el mismo sitio.

Es la orden «alias» de maquita-sitios (deploy/sitios/lib/alias.py), la misma del panel general, con un límite
más: cada alias tiene que ser uno de los dominios asignados a quien lo pide, o un subdominio suyo. Los nombres
reservados (correo, panel, portales) dan 403 y los que ya usa otro sitio, 409, sin decir de qué sitio es.
La lista que llega reemplaza a la anterior: una lista vacía quita todos los alias.
"""

import glob
import json
import os

import alcance
import rutas
import sesion
from errores import ErrorPortal
from ordenes_sitios import b64, sitios

MAXIMO = 10
TIEMPO = 600  # con HTTPS, el certificado se amplía con los alias nuevos (certbot)


def _alias_de_otro(nombre, propio):
    """¿Lo muestra ya OTRO sitio como alias?"""
    for ruta in glob.glob(os.path.join(rutas.META_SITIOS, "*.json")):
        if os.path.basename(ruta)[:-5] == propio:
            continue
        try:
            with open(ruta) as f:
                if nombre in (json.load(f).get("alias") or []):
                    return True
        except (OSError, ValueError):
            continue
    return False


def _limpio(valor):
    nombre = valor.strip().lower() if isinstance(valor, str) else ""
    if nombre.startswith("www."):
        nombre = nombre[4:]
    if not alcance.RE_DOMINIO.fullmatch(nombre):
        raise ErrorPortal(400, f"Nombre no válido: {str(valor)[:80]}")
    return nombre


def alias(ctx):
    lista = ctx.args.get("alias")
    if not isinstance(lista, list) or len(lista) > MAXIMO:
        raise ErrorPortal(400, f"Se admiten hasta {MAXIMO} alias por sitio")
    portales = None
    limpias = []
    for valor in lista:
        nombre = _limpio(valor)
        if nombre == ctx.sitio or nombre in limpias:
            continue
        if not any(alcance.en_alcance(nombre, d) for d in ctx.admin["dominios"]):
            raise ErrorPortal(400, f"{nombre} no es de sus dominios: un alias tiene que ser uno de los dominios que "
                                   "administra o un subdominio suyo")
        if portales is None:
            portales = sesion.nombres_de_portales()
        alcance.comprobar_reservado(nombre, portales)
        if alcance.sitio_existe(nombre):
            raise ErrorPortal(409, f"{nombre} ya es un sitio: no puede ser también un alias")
        if _alias_de_otro(nombre, ctx.sitio):
            raise ErrorPortal(409, f"{nombre} ya lo usa otro sitio de este servidor")
        limpias.append(nombre)
    return sitios("alias", ctx.sitio, b64(json.dumps(limpias)), tiempo=TIEMPO)


ORDENES = {"alias": ("sitio", alias)}
