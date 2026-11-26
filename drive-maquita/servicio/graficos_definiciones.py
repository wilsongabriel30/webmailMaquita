# -*- coding: utf-8 -*-
"""Cómo es DE VERDAD cada gráfico de una hoja de Google (20/10/2026).

El .xlsx que exporta Google pierde parte del gráfico: la «leyenda etiquetada»
del pastel (nombre y porcentaje junto a cada porción), qué porción lleva cada
color, si los números van encima de la barra, dónde va la leyenda… La
exportación HTML (zip) del mismo libro, en cambio, trae la definición
completa de cada gráfico para el motor de gráficos de Google:

    chartData['1794748335'] = {'chartId': …, 'chartJson': '{…}', …}
    posObj('1619987231', 'embed_1794748335', 107, 6, 102, 15)

Aquí se lee esa exportación y se guarda, por gráfico: la hoja, el tipo
(PieChart, ColumnChart…), las opciones que difieren de las de Google por
defecto, las columnas (con su formato de número) y las filas de datos que
Google dibuja, más el ancla en la hoja. `graficos_espejo.py` la usa para que
el editor del Drive lo dibuje igual. Solo biblioteca estándar.

Uso:  graficos_definiciones.py <exportación.zip> [salida.json]
"""
import json
import re
import sys
import zipfile

_GRAFICO = re.compile(
    r"chartData\['(\d+)'\] = \{'chartId': '\d+', 'elementId': '([^']+)', "
    r"'chartJson': '((?:[^'\\]|\\.)*)'", re.S)
_ANCLA = re.compile(r"posObj\('(\d+)', '([^']+)', (\d+), (\d+), (-?\d+), (-?\d+)\)")
_ESCAPE = {'n': '\n', 't': '\t', 'r': '\r', 'b': '\b', 'f': '\f', 'v': '\v', '0': '\0'}


def cadena_js(texto):
    """El valor de una cadena de JavaScript entre comillas simples (sin las comillas)."""
    salida, i = [], 0
    while i < len(texto):
        letra = texto[i]
        if letra != '\\' or i + 1 == len(texto):
            salida.append(letra)
            i += 1
            continue
        siguiente = texto[i + 1]
        if siguiente == 'x':
            salida.append(chr(int(texto[i + 2:i + 4], 16)))
            i += 4
        elif siguiente == 'u':
            salida.append(chr(int(texto[i + 2:i + 6], 16)))
            i += 6
        else:
            salida.append(_ESCAPE.get(siguiente, siguiente))
            i += 2
    return ''.join(salida)


def de_html(texto, hoja):
    """Las definiciones de los gráficos de UNA hoja exportada a HTML."""
    anclas = {m.group(2): [int(m.group(n)) for n in (3, 4, 5, 6)] for m in _ANCLA.finditer(texto)}
    salida = []
    for m in _GRAFICO.finditer(texto):
        try:
            grafico = json.loads(cadena_js(m.group(3)))
        except ValueError:
            continue
        tabla = grafico.get('dataTable') or {}
        columnas = [{'etiqueta': c.get('label', ''), 'tipo': c.get('type', ''), 'formato': c.get('pattern', '')}
                    for c in tabla.get('cols') or []]
        filas = [[(celda or {}).get('v') for celda in (fila.get('c') or [])] for fila in tabla.get('rows') or []]
        fila, columna, dx, dy = anclas.get(m.group(2), [None, None, 0, 0])
        opciones = grafico.get('options') or {}
        salida.append({
            'hoja': hoja, 'id': m.group(1), 'tipo': grafico.get('chartType', ''),
            'opciones': opciones, 'columnas': columnas, 'filas': filas,
            'vista': (grafico.get('view') or {}).get('columns'),
            'ancla': {'fila': fila, 'columna': columna, 'dx': dx, 'dy': dy,
                      'ancho': opciones.get('width'), 'alto': opciones.get('height')},
        })
    return salida


def de_exportacion(zip_html):
    """Todas las definiciones de una exportación HTML de Google (ruta o flujo)."""
    salida = []
    with zipfile.ZipFile(zip_html) as z:
        for nombre in z.namelist():
            if '/' in nombre or not nombre.endswith('.html'):
                continue
            texto = z.read(nombre).decode('utf-8', 'replace')
            if "chartData['" in texto:
                salida.extend(de_html(texto, nombre[:-5]))
    return salida


def misma_hoja(nombre_html, nombre_hoja):
    """El nombre del HTML pierde lo que no vale en un archivo («8 eval/audi» → «8 eval audi»)."""
    simple = lambda t: re.sub(r'\W+', '', t or '').lower()
    return simple(nombre_html) == simple(nombre_hoja)


def cargar(ruta):
    """Las definiciones guardadas, o [] si no hay o no se pueden leer."""
    try:
        with open(ruta, encoding='utf-8') as archivo:
            datos = json.load(archivo)
        return datos if isinstance(datos, list) else []
    except (OSError, ValueError):
        return []


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    definiciones = de_exportacion(sys.argv[1])
    texto = json.dumps(definiciones, ensure_ascii=False, indent=1)
    if len(sys.argv) > 2:
        with open(sys.argv[2], 'w', encoding='utf-8') as archivo:
            archivo.write(texto)
        print('%d gráfico(s)' % len(definiciones))
    else:
        print(texto)
