# -*- coding: utf-8 -*-
"""Las pestañas de provincia se llenan solas desde la hoja de respuestas.

Cada pestaña (BOLIVAR, CHIMBORAZO…) pasa a traer con FÓRMULAS las filas de la
hoja «Prueba IFO» cuya provincia es la suya. Así, cada respuesta nueva del
formulario aparece sola en su provincia, sin copiar y pegar.

Cómo:
  · Una celda de servicio con el nombre de la provincia TAL COMO lo escribe el
    formulario («Bolivar», «Los Ríos»…), que no siempre es el de la pestaña.
  · Una columna de servicio con el número de la n-ésima fila de esa provincia
    (AGREGAR 15/6: la k-ésima más pequeña, saltando errores).
  · Cada columna que viene del formulario: ÍNDICE sobre esa fila. Las columnas
    propias de la persona (los TOTAL, DURACIÓN) NO se tocan: conservan su
    fórmula, arrastrada a las filas nuevas.
  · La tabla de la pestaña se amplía a FILAS filas insertando dentro (única
    forma de que una tabla crezca desde la Api, comprobado el 21/09/2026).

Uso:
    python formulas_provincias.py <usuario> <ruta en el Drive> [--aplicar]

Sin `--aplicar` deja el resultado en /tmp/reconectar-ifo/provincias.xlsx y no
toca nada del Drive.

Autoría: Equipo de Tecnología Maquita — 2026-09-21
"""
import io
import os
import re
import secrets
import sys
import time
import unicodedata

sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')

import openpyxl
import requests

import nucleo_archivos as nucleo
from api_onlyoffice import firmar_jwt, url_interna_ds, _reescribir_url_interna
from config_almacen import URL_PUBLICA
from encuestas_hoja_recalculo import CARPETA_SCRIPTS, URL_SCRIPTS

HOJA_BASE = 'Prueba IFO'
FILA_CABECERAS_BASE = 4
FILA_CABECERAS_PESTANA = 5
FILAS = 100                  # filas preparadas en cada provincia
COL_CLAVE = 'CB'             # celda de servicio: nombre de la provincia
COL_INDICE = 'CC'            # columna de servicio: qué fila de la base toca
ULTIMA_BASE = 1005           # hasta dónde miran las fórmulas en la hoja base

# El nombre de la pestaña no siempre es el que guarda el formulario.
CLAVES = {'BOLIVAR': 'Bolivar', 'CHIMBORAZO': 'Chimborazo', 'COTOPAXI': 'Cotopaxi',
          'EL ORO': 'El Oro', 'ESMERALDAS': 'Esmeraldas', 'GUAYAS': 'Guayas',
          'LOS RÍOS': 'Los Ríos', 'MANABÍ': 'Manabí', 'NAPO': 'Napo',
          'PICHINCHA': 'Pichincha'}

# Columnas de la pestaña con otro nombre que su pregunta en la hoja base.
EQUIVALENCIAS = {'HECTAREAS POR PERSONAS': 'PROMEDIO'}


def plano(texto):
    sin = unicodedata.normalize('NFKD', str(texto or ''))
    sin = ''.join(c for c in sin if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', sin).strip().upper()


def letra(n):                      # 1 → A
    salida = ''
    while n > 0:
        n, resto = divmod(n - 1, 26)
        salida = chr(65 + resto) + salida
    return salida


def leer_estructura(fisica):
    """{pestaña: {columna de la pestaña: columna de la base}} y dónde acaba cada una."""
    libro = openpyxl.load_workbook(fisica)
    base = libro[HOJA_BASE]
    columnas_base = {}
    for c in range(1, 80):
        valor = base.cell(row=FILA_CABECERAS_BASE, column=c).value
        if valor:
            columnas_base.setdefault(plano(valor), c)

    salida = {}
    for nombre in libro.sheetnames:
        if nombre == HOJA_BASE:
            continue
        hoja = libro[nombre]
        mapa, propias = {}, []
        for c in range(1, 80):
            titulo = hoja.cell(row=FILA_CABECERAS_PESTANA, column=c).value
            if not titulo:
                continue
            clave = plano(titulo)
            clave = EQUIVALENCIAS.get(clave, clave)
            if clave in columnas_base:
                mapa[c] = columnas_base[clave]
            else:
                propias.append((c, str(titulo)))
        ultima = FILA_CABECERAS_PESTANA
        for f in range(FILA_CABECERAS_PESTANA + 1, hoja.max_row + 1):
            if any(hoja.cell(row=f, column=c).value not in (None, '') for c in mapa):
                ultima = f
        # Columnas de fecha (para que la fórmula no las muestre como número) y
        # fórmula de cada columna propia, tal como la tiene hoy la persona.
        fechas = [c for c, cb in mapa.items()
                  if _es_fecha(base.cell(row=FILA_CABECERAS_BASE + 1, column=cb))]
        formulas = {}
        for c, _ in propias:
            for f in range(FILA_CABECERAS_PESTANA + 1, ultima + 1):
                valor = hoja.cell(row=f, column=c).value
                if isinstance(valor, str) and valor.startswith('='):
                    formulas[c] = valor
                    break
        salida[nombre] = {'mapa': mapa, 'propias': propias, 'ultima': ultima,
                          'fechas': fechas, 'formulas': formulas,
                          'ancho': max(list(mapa) + [c for c, _ in propias] or [1])}
    return salida


def _es_fecha(celda):
    formato = str(celda.number_format or '')
    return ('yy' in formato or 'mmm' in formato) and celda.value is not None


def guion_para(nombre, datos, url_libro):
    """El trozo de docbuilder que deja una pestaña funcionando con fórmulas."""
    # Las llaves se comparan sin tildes: «MANABÍ» y «LOS RÍOS» se saltaban en
    # silencio porque `plano()` las deja como MANABI y LOS RIOS (21/09/2026).
    clave = {plano(k): v for k, v in CLAVES.items()}.get(plano(nombre))
    if not clave:
        return ''
    primera = FILA_CABECERAS_PESTANA + 1
    ultima = datos['ultima'] if datos['ultima'] > FILA_CABECERAS_PESTANA else primera
    lineas = ['var hoja = Api.GetSheet(%s);' % _js(nombre),
              'if (hoja) {',
              '  hoja.GetRange("%s%d").SetValue(%s);'
              % (COL_CLAVE, FILA_CABECERAS_PESTANA - 1, _js(clave)),
              '  hoja.GetRange("%s%d").SetValue(%s);'
              % (COL_CLAVE, FILA_CABECERAS_PESTANA - 2,
                 _js('Provincia tal como la guarda el formulario. No borrar.'))]

    faltan = FILAS - (ultima - FILA_CABECERAS_PESTANA)
    if faltan > 0:
        # Insertar DENTRO de la tabla: es la única forma de que crezca de verdad.
        lineas.append('  hoja.GetRange("A%d:%s%d").Insert("down");'
                      % (ultima, letra(datos['ancho']), ultima + faltan - 1))
        # La fila que se desplazó vuelve a su sitio y presta sus fórmulas al bloque.
        lineas.append('  hoja.GetRange("A%d:%s%d").Copy(hoja.GetRange("A%d"));'
                      % (ultima + faltan, letra(datos['ancho']), ultima + faltan, ultima))
        lineas.append('  hoja.GetRange("A%d:%s%d").Copy(hoja.GetRange("A%d:%s%d"));'
                      % (ultima, letra(datos['ancho']), ultima,
                         ultima + 1, letra(datos['ancho']), ultima + faltan))

    fin = FILA_CABECERAS_PESTANA + FILAS
    rango_base = "'%s'!$A$%d:$A$%d" % (HOJA_BASE, FILA_CABECERAS_BASE + 1, ULTIMA_BASE)
    col_prov = letra(datos['mapa'].get(3, 3))
    for fila in range(primera, fin + 1):
        indice = ('=IFERROR(AGGREGATE(15,6,(ROW(%s)-%d)/(\'%s\'!$%s$%d:$%s$%d=$%s$%d),ROW()-%d),"")'
                  % (rango_base, FILA_CABECERAS_BASE, HOJA_BASE, col_prov,
                     FILA_CABECERAS_BASE + 1, col_prov, ULTIMA_BASE,
                     COL_CLAVE, FILA_CABECERAS_PESTANA - 1, FILA_CABECERAS_PESTANA))
        lineas.append('  hoja.GetRange("%s%d").SetValue(%s);' % (COL_INDICE, fila, _js(indice)))
        for columna, columna_base in sorted(datos['mapa'].items()):
            origen = "'%s'!%s$%d:%s$%d" % (HOJA_BASE, letra(columna_base),
                                           FILA_CABECERAS_BASE + 1,
                                           letra(columna_base), ULTIMA_BASE)
            formula = ('=IF($%s%d="","",IF(INDEX(%s,$%s%d)="","",INDEX(%s,$%s%d)))'
                       % (COL_INDICE, fila, origen, COL_INDICE, fila, origen, COL_INDICE, fila))
            lineas.append('  hoja.GetRange("%s%d").SetValue(%s);'
                          % (letra(columna), fila, _js(formula)))
    # Formato de fecha donde la hoja base lo lleva; si no, saldría el número.
    for columna in datos.get('fechas', []):
        formato = 'dd/mm/yyyy hh:mm' if columna == 1 else 'dd/mm/yyyy'
        lineas.append('  hoja.GetRange("%s%d:%s%d").SetNumberFormat("%s");'
                      % (letra(columna), primera, letra(columna), fin, formato))
    # Las columnas propias (TOTAL, DURACIÓN) se blindan contra celdas vacías:
    # una resta de fechas que aún no existen daba «#¡VALOR!» en las filas que
    # todavía no tienen respuesta (21/09/2026).
    for columna, formula in datos.get('formulas', {}).items():
        cuerpo = formula[1:]
        if cuerpo.upper().startswith(('IFERROR', 'SI.ERROR')):
            blindada = formula
        else:
            blindada = '=IFERROR(%s,"")' % cuerpo
        for fila in range(primera, fin + 1):
            lineas.append('  hoja.GetRange("%s%d").SetValue(%s);'
                          % (letra(columna), fila, _js(blindada)))
    lineas.append('}')
    return '\n'.join(lineas)


def _js(texto):
    """Texto para el guion del editor, con los acentos en \\uXXXX.

    El docbuilder no lee el guion como UTF-8: los nombres con tilde («MANABÍ»,
    «LOS RÍOS») no encontraban su hoja y esas dos pestañas se quedaban sin
    fórmulas (21/09/2026). Escapados, llegan bien.
    """
    salida = []
    for caracter in str(texto):
        if caracter == '\\':
            salida.append('\\\\')
        elif caracter == '"':
            salida.append('\\"')
        elif ord(caracter) < 128:
            salida.append(caracter)
        else:
            salida.append('\\u%04x' % ord(caracter))
    return '"%s"' % ''.join(salida)


def principal(usuario, ruta, aplicar):
    fisica = nucleo.ruta_fisica(usuario, ruta)
    estructura = leer_estructura(fisica)
    for nombre, datos in estructura.items():
        print('  %-12s %2d columnas del formulario, %d propias, datos hasta la fila %d'
              % (nombre, len(datos['mapa']), len(datos['propias']), datos['ultima']))

    token = firmar_jwt({'u': usuario, 'r': ruta, 'uso': 'descarga',
                        'exp': int(time.time()) + 600})
    url_libro = '%s/api/almacen/onlyoffice/download?t=%s' % (URL_PUBLICA, token)
    partes = ['builder.OpenFile("%s");' % url_libro]
    for nombre, datos in estructura.items():
        partes.append(guion_para(nombre, datos, url_libro))
    partes += ['Api.RecalculateAllFormulas();',
               'builder.SaveFile("xlsx", "provincias.xlsx");', 'builder.CloseFile();']

    os.makedirs(CARPETA_SCRIPTS, exist_ok=True)
    fichero = secrets.token_hex(16) + '.docbuilder'
    camino = os.path.join(CARPETA_SCRIPTS, fichero)
    open(camino, 'w', encoding='utf-8').write('\n'.join(partes) + '\n')
    os.chmod(camino, 0o644)
    print('  guion de %d líneas' % len('\n'.join(partes).splitlines()))
    try:
        cuerpo = {'async': False, 'key': 'prov' + secrets.token_hex(8),
                  'url': '%s%s/%s' % (URL_PUBLICA, URL_SCRIPTS, fichero)}
        cuerpo['token'] = firmar_jwt(dict(cuerpo))
        respuesta = requests.post(
            url_interna_ds().rstrip('/') + '/docbuilder', json=cuerpo, timeout=(3, 600),
            headers={'Authorization': 'Bearer ' + firmar_jwt({'payload': cuerpo})})
        urls = list((respuesta.json() or {}).get('urls', {}).values())
        if not urls:
            print('  el docbuilder respondió:', respuesta.status_code, respuesta.text[:300])
            return 1
        salida = requests.get(_reescribir_url_interna(urls[0]), timeout=(3, 120)).content
        destino = '/tmp/reconectar-ifo/provincias.xlsx'
        open(destino, 'wb').write(salida)
        print('  resultado en', destino, '(%.0f KB)' % (len(salida) / 1024))
        if aplicar:
            import sala_editor
            from api_onlyoffice import _base_documento, invalidar_cache
            dentro = sala_editor.usuarios_conectados(_base_documento(usuario, ruta))
            if dentro is None or dentro:
                print('  NO se aplica: el Excel está abierto en el editor (%s)' % dentro)
                return 2
            carpeta, _, nombre_archivo = ruta.rpartition('/')
            nucleo.subir(usuario, carpeta or '/', nombre_archivo, io.BytesIO(salida))
            invalidar_cache(usuario, ruta)
            print('  aplicado al archivo del Drive (la versión anterior queda en el historial)')
    finally:
        os.remove(camino)
    return 0


if __name__ == '__main__':
    sys.exit(principal(int(sys.argv[1]), sys.argv[2], '--aplicar' in sys.argv))
