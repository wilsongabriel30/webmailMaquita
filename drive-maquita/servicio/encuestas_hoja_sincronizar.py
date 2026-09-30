# -*- coding: utf-8 -*-
"""
Formularios del Almacén — la hoja refleja las respuestas, no solo las nuevas
============================================================================
Desde el 17/09/2026 el motor solo AÑADE filas al final de la tabla. Eso respeta
el trabajo de la persona (pestañas, fórmulas, columnas propias), pero deja fuera
dos cosas que la gente hace a diario (comprobado con `pruebas/prueba_flujo_hoja.py`
el 22/09/2026):

  · **modificar una respuesta** — la fila vieja se quedaba y la corregida se
    añadía otra vez, así que la respuesta salía DUPLICADA;
  · **borrar una respuesta** — su fila seguía en el Excel para siempre.

Aquí está la reconciliación: comparar lo que hay escrito con lo que hay en la
base y, si no coinciden, reescribir las filas de datos en su sitio y vaciar las
que sobren. Se tocan **solo las columnas de las preguntas**: las columnas
propias de la persona (TOTAL, DURACIÓN) conservan su fórmula, y las pestañas,
los formatos y el resto del libro no se tocan.

El camino barato sigue siendo el de siempre: si lo escrito coincide y solo hay
respuestas nuevas, se añaden al final sin reescribir nada.

Autoría: Equipo de Tecnología Maquita — 2026-09-22
"""
import io
import logging
import re
import zipfile
from datetime import datetime, timedelta

from encuestas_hoja_xml import (RE_CELDA, RE_FILA, _buscar_tabla, _cadenas, _celda_valor,
                                _col_letras, _filas, _rango, _texto_celda, _tupla)

log = logging.getLogger('almacen.encuestas.hoja_sincronizar')


def _serial(momento):
    """La fecha como la guarda Excel (número de días desde 1899-12-30)."""
    if not momento:
        return None
    limpio = momento.replace(tzinfo=None, microsecond=0)
    return (limpio - datetime(1899, 12, 30)).total_seconds() / 86400.0


def _mismo_instante(texto, momento):
    """¿La celda de «Fecha» es esa respuesta? Al segundo: el editor guarda la
    fecha como número y al releerla bailan los microsegundos."""
    if momento is None:
        return texto in (None, '')
    try:
        leido = datetime(1899, 12, 30) + timedelta(days=float(texto))
    except (TypeError, ValueError):
        return False
    return abs((leido - momento.replace(tzinfo=None)).total_seconds()) < 1.5


def _iguales(escrito, esperado):
    if esperado is None:                      # columna de la persona: no se mira
        return True
    if isinstance(esperado, datetime):
        return _mismo_instante(escrito, esperado)
    if isinstance(esperado, (int, float)) and not isinstance(esperado, bool):
        try:
            return abs(float(escrito) - float(esperado)) < 1e-9
        except (TypeError, ValueError):
            return False
    return str(escrito or '') == str(esperado or '')


def revisar(filas_hoja, filas_esperadas):
    """(hay_desfase, cuántas filas ya están bien desde el principio).

    Un desfase es una fila que no cuadra con la respuesta que le toca o una fila
    de más: modificaron o borraron algo. Si todo cuadra y solo faltan filas al
    final, no hace falta reescribir nada.
    """
    comunes = min(len(filas_hoja), len(filas_esperadas))
    for i in range(comunes):
        escritos, esperados = filas_hoja[i], filas_esperadas[i]
        for j, esperado in enumerate(esperados):
            escrito = escritos[j] if j < len(escritos) else ''
            if not _iguales(escrito, esperado):
                return True, i
    if len(filas_hoja) > len(filas_esperadas):
        return True, len(filas_esperadas)     # sobran filas: borraron respuestas
    return False, comunes


def escribir(contenido, filas_esperadas, columnas_datos):
    """El `.xlsx` con las filas de datos puestas al día.

    `filas_esperadas`: una lista por respuesta, alineada con las columnas de la
    tabla; `None` en una posición = columna de la persona, no se toca.
    `columnas_datos`: posiciones (0..n dentro del rango) que el motor gobierna;
    en las filas que sobran se vacían solo esas.
    """
    zin = zipfile.ZipFile(io.BytesIO(contenido))
    parte_hoja, parte_tabla = _buscar_tabla(zin)
    xml_hoja = zin.read(parte_hoja).decode('utf-8')
    xml_tabla = zin.read(parte_tabla).decode('utf-8')
    c1, f1, c2, f2 = _rango(re.search(r'\bref="([^"]+)"', xml_tabla).group(1))
    filas = _filas(xml_hoja)
    cadenas = _cadenas(zin)

    # Hasta dónde hay filas escritas hoy (para saber cuáles hay que vaciar).
    ultima = f1
    for n, fila in filas.items():
        if n > f1 and any(c1 <= c <= c2 and (interior or '').strip()
                          for c, (_, _, interior) in fila['celdas'].items()):
            ultima = max(ultima, n)

    def estilo_de(fila_n, columna):
        celda = filas.get(fila_n, {}).get('celdas', {}).get(columna)
        encontrado = re.search(r'\bs="(\d+)"', (celda or ('', '', ''))[1] or '')
        return encontrado.group(1) if encontrado else None

    tocadas = 0
    for i, valores in enumerate(filas_esperadas):
        numero = f1 + 1 + i
        fila = filas.setdefault(numero, {'atributos': '', 'celdas': {}})
        for j, columna in enumerate(range(c1, c2 + 1)):
            esperado = valores[j] if j < len(valores) else None
            if esperado is None:
                continue                      # columna de la persona
            celda = fila['celdas'].get(columna)
            actual = _texto_celda(celda[1], celda[2], cadenas) if celda else ''
            if _iguales(actual, esperado):
                continue
            coordenada = '%s%d' % (_col_letras(columna), numero)
            fila['celdas'][columna] = _tupla(
                _celda_valor(coordenada, estilo_de(numero, columna), esperado))
            tocadas += 1

    # Las filas que sobran (respuestas borradas) se vacían en las columnas del
    # motor; las de la persona se quedan con su fórmula.
    for numero in range(f1 + 1 + len(filas_esperadas), ultima + 1):
        fila = filas.get(numero)
        if not fila:
            continue
        for j in columnas_datos:
            columna = c1 + j
            celda = fila['celdas'].get(columna)
            if not celda or not (celda[2] or '').strip():
                continue
            fila['celdas'][columna] = _tupla(_celda_valor(
                '%s%d' % (_col_letras(columna), numero), estilo_de(numero, columna), ''))
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
    # Que el editor recalcule al abrir: los TOTAL de las filas tocadas cambian.
    xml_libro = zin.read('xl/workbook.xml').decode('utf-8')
    if '<calcPr' in xml_libro:
        if 'fullCalcOnLoad' not in xml_libro:
            xml_libro = xml_libro.replace('<calcPr', '<calcPr fullCalcOnLoad="1"', 1)
    else:
        ancla = '<extLst' if '<extLst' in xml_libro else '</workbook>'
        xml_libro = xml_libro.replace(ancla, '<calcPr fullCalcOnLoad="1"/>' + ancla, 1)

    cambiadas = {parte_hoja: xml_hoja, 'xl/workbook.xml': xml_libro}
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            zout.writestr(info, cambiadas[info.filename].encode('utf-8')
                          if info.filename in cambiadas else zin.read(info.filename))
    log.info('hoja sincronizada: %d celdas', tocadas)
    return salida.getvalue()
