# -*- coding: utf-8 -*-
"""
URLs del Document Server — traducción y allowlist.
==================================================
Al terminar de editar, el Document Server avisa al Almacén con la URL desde la
que hay que descargar el documento guardado. Esa URL la construye con **el
dominio por el que le llegó la petición**, y el Drive vive en DOS dominios
(`intranet.example.org` y `nube.example.org`) que apuntan al mismo servidor.

Quien editaba desde `drive` recibía una URL de `drive`, que no coincidía con la
única base configurada (`datos`), la allowlist la rechazaba y el guardado
fallaba con «Se ha producido un error al guardar el archivo». 192 guardados
rechazados entre el 24 y el 31 de agosto de 2026, todos de `drive`.

Aquí se decide, en un solo sitio y sin tocar la base de datos, qué URL es
realmente del Document Server y cómo se traduce a su dirección interna. Sigue
siendo una allowlist: lo que no venga del Document Server se rechaza, y la
descarga se hace SIEMPRE contra la dirección interna, nunca contra el dominio
público que anuncia el propio Document Server.

Drive único (28/10/2026): el Drive también se abre desde el correo, por
`https://mail.<dominio>/office-almacen` (o `/office-lectura`), y los dominios del
correo pueden crecer (uno por cada dominio de correo, los que
vengan). En vez de una lista fija, se reconoce esa forma: `base_del_correo()`. La
descarga sigue yendo por la dirección interna, nunca por el dominio anunciado.

Autoría: Equipo de Tecnología Maquita — 2026-08-31
"""
import re

# https://mail.<dominio>/office-almacen | /office-lectura  (el prefijo bajo el que el
# nginx del correo reenvía el Document Server a Raíces).
_BASE_CORREO = re.compile(
    r'^https://mail\.[a-z0-9-]+(?:\.[a-z0-9-]+)+/office-(?:almacen|lectura)(?=/|$)')


def base_del_correo(url: str):
    """La base del Document Server anunciada por un dominio del correo, o None."""
    coincidencia = _BASE_CORREO.match((url or '').strip())
    return coincidencia.group(0) if coincidencia else None


def bases_publicas(url_publica: str, extra: str = '') -> list:
    """Todas las bases públicas por las que el Document Server puede anunciarse.

    `url_publica` es la principal (config_kv `onlyoffice_url_publica`) y `extra`
    la lista separada por comas de las demás (`onlyoffice_urls_publicas_extra`),
    que es donde vive el segundo dominio del Drive.
    """
    bases = []
    for candidata in [url_publica] + (extra or '').split(','):
        candidata = (candidata or '').strip().rstrip('/')
        if candidata and candidata not in bases:
            bases.append(candidata)
    return bases


def a_url_interna(url: str, bases: list, interna: str):
    """La URL con la que descargar el documento, o None si no es del DS.

    Devolver None es la respuesta a «esto no lo publicó nuestro Document
    Server»: es la defensa contra que un tercero nos haga descargar de donde
    quiera (SSRF). Si hay dirección interna, la descarga va por ella aunque el
    aviso llegara con un dominio público.
    """
    url = (url or '').strip()
    interna = (interna or '').rstrip('/')
    if not url:
        return None
    for base in bases:
        base = base.rstrip('/')
        if url == base or url.startswith(base + '/'):
            return (interna + url[len(base):]) if interna else url
    # Puede llegar ya en su forma interna (el DS configurado sin dominio
    # público): también es del Document Server.
    if interna and (url == interna or url.startswith(interna + '/')):
        return url
    # Anunciada por un dominio del correo: solo si hay dirección interna por la
    # que descargar (así nunca se descarga de un dominio que no controlamos).
    base = base_del_correo(url)
    if base and interna:
        return interna + url[len(base):]
    return None


def base_para_navegador(url_publica: str) -> str:
    """Base con la que el NAVEGADOR pide lo que sirve Raíces al editor (los complementos
    propios): el dominio por el que entró la persona —datos, drive o mail.<dominio> del
    correo—, no uno fijo, o el navegador lo bloquea (CORS). Fuera de una petición, o si no
    es https, la base configurada."""
    try:
        from flask import request
        base = request.host_url.rstrip('/')
    except Exception:
        return (url_publica or '').rstrip('/')
    return base if base.startswith('https://') else (url_publica or '').rstrip('/')
