# -*- coding: utf-8 -*-
"""
Título interno de un archivo, para poder buscarlo por él.
=========================================================
Hay documentos cuyo NOMBRE de archivo no dice nada porque lo pone el sistema, y
cuyo título de verdad vive dentro. El caso claro son los formularios del Drive:
el botón «+ Nuevo» los llama a todos «Nuevo Formulario 3.forma», así que buscar
«encuesta» no encontraba la «Encuesta Diagnóstica» de nadie — y la persona que la
creó da por hecho que la va a encontrar por ese nombre, porque es el que ve en
grande al abrirla.

Este módulo devuelve ese título para que el índice de nombres lo guarde junto al
nombre del archivo. Va aparte porque la lista de formatos con título interno va a
crecer (los diagramas y las hojas de cálculo también lo tienen), y porque así el
índice de nombres no necesita saber leer ningún formato.

Regla: si algo falla, se devuelve cadena vacía. Un título que no se puede leer
solo significa que ese archivo se busca únicamente por su nombre, nunca que la
indexación se rompa.

Autoría: Equipo de Tecnología Maquita — 2026-08-27
"""
import json
import logging
import re

log = logging.getLogger('almacen.titulos')

# Formatos que llevan un título dentro y cuyo nombre de archivo no lo refleja.
EXTENSIONES_CON_TITULO = {'forma'}

MAXIMO = 300   # lo que cabe de sobra en un título; corta los archivos raros


def titulo_de(fisica: str, extension: str) -> str:
    """Título interno del archivo, o '' si no tiene o no se pudo leer."""
    extension = (extension or '').lower()
    if extension not in EXTENSIONES_CON_TITULO:
        return ''
    try:
        if extension == 'forma':
            return _titulo_de_formulario(fisica)
    except Exception as excepcion:
        log.debug('titulos: no se pudo leer %s (%s)', fisica, excepcion)
    return ''


def _titulo_de_formulario(fisica: str) -> str:
    """Título de un `.forma`. Se le quitan las etiquetas de formato: un título
    escrito como «<b>Encuesta</b>» tiene que encontrarse buscando «encuesta»."""
    with open(fisica, encoding='utf-8') as archivo:
        definicion = json.load(archivo)
    if not isinstance(definicion, dict):
        return ''
    titulo = definicion.get('titulo')
    if not isinstance(titulo, str):
        return ''
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', titulo)).strip()[:MAXIMO]
