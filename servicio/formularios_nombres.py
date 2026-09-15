# -*- coding: utf-8 -*-
"""Nombres que usa un formulario creado desde un libro (10/09/2026).

Google Sheets llama a la hoja de respuestas como al formulario, y eso es lo que
la gente espera ver: «Encuesta de clima», no «Respuestas 2». Aquí se decide:

- `nombre_hoja(titulo)`: el título del formulario convertido en un nombre de
  hoja válido para Excel (31 caracteres como mucho, sin `[]:*?/\\`), quitando
  el prefijo «Formulario de » que pone el botón cuando el formulario nace de
  un libro llamado así.
- `hoja_libre(usadas, base)`: el primer nombre que no exista ya en el libro
  («Nombre», «Nombre (2)», «Nombre (3)»…), respetando el límite de 31.
- `carpeta_respuestas(carpeta)`: dónde va el archivo maestro de respuestas —
  una carpeta interna, oculta, dentro de la carpeta del libro—, de modo que en
  el Drive solo se ven DOS archivos: el Excel y el formulario.
"""
import re

from archivos_internos import CARPETA_RESPUESTAS

LARGO_MAXIMO_HOJA = 31          # límite de Excel
PREFIJO_TITULO = 'Formulario de '
_CARACTERES_PROHIBIDOS = re.compile(r'[\[\]:*?/\\]')


def nombre_hoja(titulo):
    """Título del formulario → nombre de hoja válido en Excel."""
    texto = (titulo or '').strip()
    if texto.lower().startswith(PREFIJO_TITULO.lower()):
        texto = texto[len(PREFIJO_TITULO):].strip()
    texto = _CARACTERES_PROHIBIDOS.sub(' ', texto)
    texto = re.sub(r'\s+', ' ', texto).strip().strip("'")
    if not texto:
        texto = 'Respuestas'
    return texto[:LARGO_MAXIMO_HOJA].rstrip()


def hoja_libre(usadas, base):
    """Primer nombre libre a partir de `base` dentro del conjunto `usadas`.

    Excel no distingue mayúsculas en los nombres de hoja, así que aquí tampoco.
    """
    usadas = {(u or '').lower() for u in usadas}
    if base.lower() not in usadas:
        return base
    numero = 2
    while True:
        sufijo = ' (%d)' % numero
        candidato = base[:LARGO_MAXIMO_HOJA - len(sufijo)].rstrip() + sufijo
        if candidato.lower() not in usadas:
            return candidato
        numero += 1


def carpeta_respuestas(carpeta):
    """La carpeta interna (oculta) donde va el archivo maestro de respuestas."""
    return ('' if carpeta == '/' else carpeta) + '/' + CARPETA_RESPUESTAS


def nombre_archivo_respuestas(titulo):
    """Nombre del archivo maestro, igual que lo llamaba «Exportar»."""
    return (titulo or 'Formulario')[:80] + ' (respuestas).xlsx'
