# -*- coding: utf-8 -*-
"""
Formularios del Almacén — vaciar la hoja cuando no queda ninguna respuesta
=========================================================================
Si se borran TODAS las respuestas de un formulario, su hoja tiene que quedar
vacía, igual que la pestaña Respuestas (28/09/2026).

Se vacían las filas que hay bajo los encabezados, en todas las columnas que
tienen encabezado: las de la tabla y las que hayan quedado a su derecha
(preguntas que se añadieron o se quitaron después). Se conservan:

  · los encabezados, los formatos y el ancho de las columnas;
  · las celdas con FÓRMULA (las columnas propias de la persona: TOTAL…),
    que se recalculan solas sobre las filas ya vacías;
  · las demás pestañas y el resto del libro.

Las respuestas no se pierden: quedan en la papelera del formulario, y el
archivo guarda su versión anterior.

Autoría: Equipo de Tecnología Maquita — 2026-09-28
"""
import io
import logging
import re
import zipfile

from encuestas_hoja_xml import (_buscar_tabla, _celda_valor, _col_letras, _filas,
                                _rango, _tupla)

log = logging.getLogger('almacen.encuestas.hoja_vaciar')


def vaciar(contenido):
    """El `.xlsx` sin filas de respuestas, o None si no había nada que vaciar."""
    zin = zipfile.ZipFile(io.BytesIO(contenido))
    parte_hoja, parte_tabla = _buscar_tabla(zin)
    xml_hoja = zin.read(parte_hoja).decode('utf-8')
    xml_tabla = zin.read(parte_tabla).decode('utf-8')
    c1, f1, c2, _f2 = _rango(re.search(r'\bref="([^"]+)"', xml_tabla).group(1))
    filas = _filas(xml_hoja)

    # Hasta qué columna hay encabezados, también fuera de la tabla.
    cabecera = (filas.get(f1) or {}).get('celdas') or {}
    ultima_columna = max([c2] + [c for c, celda in cabecera.items()
                                 if c > c2 and (celda[2] or '').strip()])

    tocadas = 0
    for numero, fila in filas.items():
        if numero <= f1:
            continue
        for columna in range(c1, ultima_columna + 1):
            celda = fila['celdas'].get(columna)
            interior = (celda[2] or '') if celda else ''
            if not interior.strip() or '<f' in interior:
                continue                      # vacía, o fórmula de la persona
            estilo = re.search(r'\bs="(\d+)"', celda[1] or '')
            fila['celdas'][columna] = _tupla(_celda_valor(
                '%s%d' % (_col_letras(columna), numero),
                estilo.group(1) if estilo else None, ''))
            tocadas += 1
    if not tocadas:
        return None

    def xml_fila(n, fila):
        celdas = ''.join(fila['celdas'][c][0] for c in sorted(fila['celdas']))
        atributos = re.sub(r'\sspans="[^"]*"', '', fila['atributos'])
        return ('<row r="%d"%s>%s</row>' % (n, atributos, celdas) if celdas
                else '<row r="%d"%s/>' % (n, atributos))
    datos = ''.join(xml_fila(n, filas[n]) for n in sorted(filas))
    xml_hoja = re.sub(r'<sheetData[^>]*?(?:/>|>.*?</sheetData>)',
                      lambda _: '<sheetData>%s</sheetData>' % datos,
                      xml_hoja, count=1, flags=re.S)
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            zout.writestr(info, xml_hoja.encode('utf-8')
                          if info.filename == parte_hoja else zin.read(info.filename))
    log.info('hoja vaciada: %d celdas', tocadas)
    return salida.getvalue()
