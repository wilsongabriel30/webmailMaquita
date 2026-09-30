# -*- coding: utf-8 -*-
"""
Formularios del Almacén — reconocer una hoja de respuestas DAÑADA
================================================================
El 29/09/2026 el complemento «respuestas en vivo» escribió sobre una tabla
vacía: cada respuesta duplicó los encabezados y pisó a la anterior. Quedó un
Excel con 56 copias de los encabezados y una sola respuesta, con 57 en la base.
Añadir filas a una tabla así no arregla nada, y encima el motor le creó todas
las columnas otra vez porque ya no reconocía ninguna.

Este módulo contesta dos preguntas, sin escribir nada:

  · `danada(contenido, conocidos)`  → ¿la tabla ya no es de fiar?
        - `encabezados`: ninguno es una columna conocida (añadir filas ahí
          crearía todas las columnas otra vez), o
        - `copias`: los encabezados están repetidos en filas por ENCIMA de la
          tabla, que es la huella de una tabla empujada hacia abajo.
  · `se_puede_rehacer(contenido)`   → ¿se puede rehacer desde la base sin
        llevarse trabajo de la persona? Solo si el libro tiene una única
        pestaña y ninguna fórmula.

Con las dos respuestas afirmativas `encuestas_hoja_libro.preparar` rehace la
hoja desde las respuestas guardadas. Si el libro tiene trabajo propio no se
toca: se deja constancia en el registro para repararlo a mano.

Autoría: Equipo de Tecnología Maquita — 2026-09-29
"""
import io
import logging
import re
import unicodedata
import zipfile

import encuestas_hoja_xml as xml_mod

log = logging.getLogger('almacen.encuestas.hoja_reparar')

# Cuántas celdas del principio de una fila tienen que coincidir con los
# encabezados para darla por una copia suya.
CELDAS_IGUALES = 3


def _normal(texto):
    plano = unicodedata.normalize('NFKD', str(texto or ''))
    plano = ''.join(c for c in plano if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', plano).strip().upper()


def danada(contenido, conocidos):
    """(clave, detalle) de por qué la tabla «Respuestas» no es de fiar, o
    ('', '') si está bien. La clave es `encabezados` o `copias`.

    `conocidos` son los nombres de columna que el motor espera encontrar
    (cabeceras fijas, títulos de las preguntas y nombres anotados).
    """
    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        parte_hoja, parte_tabla = xml_mod._buscar_tabla(z)
        c1, f1, c2, _ = xml_mod._rango(re.search(
            r'\bref="([^"]+)"', z.read(parte_tabla).decode('utf-8')).group(1))
        filas = xml_mod._filas(z.read(parte_hoja).decode('utf-8'))
        cadenas = xml_mod._cadenas(z)

    def textos(numero, hasta):
        celdas = filas.get(numero, {}).get('celdas', {})
        return [_normal(xml_mod._texto_celda(celdas[c][1], celdas[c][2], cadenas))
                if c in celdas else '' for c in range(c1, hasta + 1)]

    encabezados = textos(f1, c2)
    con_texto = [e for e in encabezados if e]
    if not con_texto:
        return 'encabezados', 'la tabla no tiene encabezados'
    esperados = {_normal(c) for c in conocidos if c}
    if esperados and not any(e in esperados for e in con_texto):
        return 'encabezados', 'ningún encabezado de la tabla es una columna del formulario'

    ancho = min(CELDAS_IGUALES, len(encabezados))
    principio = encabezados[:ancho]
    if ancho >= 2 and all(principio):
        copias = [n for n in filas
                  if n < f1 and textos(n, c1 + ancho - 1) == principio]
        if copias:
            return 'copias', ('los encabezados están repetidos en %d filas por encima '
                              'de la tabla' % len(copias))
    return '', ''


def se_puede_rehacer(contenido):
    """¿El libro es solo la hoja de respuestas, sin trabajo de la persona?"""
    try:
        with zipfile.ZipFile(io.BytesIO(contenido)) as z:
            hojas = [n for n in z.namelist()
                     if re.fullmatch(r'xl/worksheets/[^/]+\.xml', n)]
            if len(hojas) != 1:
                return False
            return b'<f' not in z.read(hojas[0])
    except Exception as excepcion:
        log.warning('no se pudo examinar el libro (%s)', excepcion)
        return False
