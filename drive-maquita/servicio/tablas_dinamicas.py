# -*- coding: utf-8 -*-
"""Tablas dinámicas de Google que el editor del Drive pueda calcular (20/10/2026).

Google exporta cada tabla dinámica con su definición (`pivotTableN.xml`) y la
de su caché (`pivotCacheDefinitionN.xml`: origen, campos y valores distintos),
pero SIN los registros de la caché (`pivotCacheRecords`) y sin las celdas del
resultado. El editor dice entonces «El informe de la tabla dinámica se ha
guardado sin los datos subyacentes» y la hoja queda en blanco (y los gráficos
que leen de ella, vacíos).

Aquí se escriben esos registros a partir del rango de origen, que sí viene en
el libro (`<worksheetSource ref="A3:O25" sheet="Consolidado"/>`): una fila por
registro, cada valor como índice de su `sharedItems` (o el valor mismo si el
campo no los enumera). Con `refreshOnLoad="1"` (Google ya lo pone) el editor
calcula la tabla al abrir y «Actualizar» vuelve a funcionar.

Lee los valores con openpyxl (solo lectura) y escribe el paquete pieza a pieza:
no toca nada más del libro.

Con `--resultados r.json` (lo baja la sincronización de la exportación HTML de
Google, tablas_dinamicas_resultado.py) se escribe además el resultado que
enseña Google en las celdas de cada tabla: así se ve sin pulsar «Actualizar».

Uso:  tablas_dinamicas.py <entrada.xlsx> <salida.xlsx> [--resultados r.json]
"""
import datetime
import json
import logging
import os
import posixpath
import re
import shutil
import sys
import zipfile
from xml.sax.saxutils import escape

log = logging.getLogger('almacen.tablas_dinamicas')

_TIPO_REGISTROS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/pivotCacheRecords'
_CONTENIDO_REGISTROS = 'application/vnd.openxmlformats-officedocument.spreadsheetml.pivotCacheRecords+xml'
_ESPACIOS = ('xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
             'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"')
_ELEMENTO = re.compile(r'<(s|n|b|e|d|m)(?:\s+v="([^"]*)")?\s*/>')
_LIMITE = 200000                                    # registros: más no compensa en una sincronización


def _atributo(texto, nombre):
    m = re.search(r'\b%s="([^"]*)"' % nombre, texto)
    return m.group(1) if m else None


def _desescapar(texto):
    return (texto.replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"')
            .replace('&apos;', "'").replace('&amp;', '&'))


def _campos(definicion):
    """[(nombre, [(tipo, valor)] o None si el campo no enumera sus valores)]."""
    salida = []
    for campo in re.finditer(r'<cacheField\b([^>]*?)(?:/>|>(.*?)</cacheField>)', definicion, re.S):
        nombre = _desescapar(_atributo(campo.group(1), 'name') or '')
        compartidos = re.search(r'<sharedItems\b[^>]*?(?:/>|>(.*?)</sharedItems>)', campo.group(2) or '', re.S)
        elementos = None
        if compartidos and compartidos.group(1):
            elementos = [(m.group(1), _desescapar(m.group(2)) if m.group(2) is not None else None)
                         for m in _ELEMENTO.finditer(compartidos.group(1))]
        salida.append((nombre, elementos))
    return salida


def _clave(tipo, valor):
    """Forma comparable de un elemento de la caché."""
    if tipo == 'm' or valor is None:
        return ('m', None)
    if tipo == 'n':
        return ('n', round(float(valor), 9))
    if tipo == 'd':
        return ('d', valor[:19])
    if tipo == 'b':
        return ('b', valor in ('1', 'true'))
    return ('s', valor)


def _clave_de_celda(valor):
    if valor is None or (isinstance(valor, str) and valor == ''):
        return ('m', None)
    if isinstance(valor, bool):
        return ('b', valor)
    if isinstance(valor, (int, float)):
        return ('n', round(float(valor), 9))
    if isinstance(valor, datetime.datetime):
        return ('d', valor.strftime('%Y-%m-%dT%H:%M:%S'))
    if isinstance(valor, datetime.date):
        return ('d', valor.strftime('%Y-%m-%dT00:00:00'))
    return ('s', str(valor))


def _en_linea(clave):
    """El valor escrito dentro del registro (campo sin lista de valores)."""
    tipo, valor = clave
    if tipo == 'm':
        return '<m/>'
    if tipo == 'n':
        return '<n v="%s"/>' % repr(valor)
    if tipo == 'b':
        return '<b v="%d"/>' % int(valor)
    return '<%s v="%s"/>' % (tipo, escape(str(valor), {'"': '&quot;'}))


def registros(definicion, filas):
    """El XML de pivotCacheRecords para esas filas de datos (sin la cabecera)."""
    campos = _campos(definicion)
    indices = []
    for _, elementos in campos:
        if elementos is None:
            indices.append(None)
            continue
        mapa = {}
        for posicion, (tipo, valor) in enumerate(elementos):
            mapa.setdefault(_clave(tipo, valor), posicion)
        indices.append(mapa)
    partes = []
    for fila in filas:
        celdas = []
        for k in range(len(campos)):
            clave = _clave_de_celda(fila[k] if k < len(fila) else None)
            mapa = indices[k]
            if mapa is not None and clave in mapa:
                celdas.append('<x v="%d"/>' % mapa[clave])
            elif mapa is not None and clave[0] == 's' and ('s', clave[1].strip()) in mapa:
                celdas.append('<x v="%d"/>' % mapa[('s', clave[1].strip())])
            else:
                celdas.append(_en_linea(clave))
        partes.append('<r>%s</r>' % ''.join(celdas))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<pivotCacheRecords %s count="%d">%s'
            '</pivotCacheRecords>' % (_ESPACIOS, len(partes), ''.join(partes))), len(partes)


def _filas_del_origen(libro, hoja, rango):
    """Las filas de datos del rango de origen (la primera es la cabecera)."""
    if hoja not in libro.sheetnames:
        return None
    filas = [list(f) for f in libro[hoja].iter_rows(values_only=True, **_limites(rango))]
    if len(filas) < 2:
        return []
    datos = filas[1:]
    while datos and all(v is None for v in datos[-1]):
        datos.pop()                                 # filas vacías al final del rango
    return datos[:_LIMITE]


def _limites(rango):
    m = re.match(r'\$?([A-Z]+)\$?(\d+):\$?([A-Z]+)\$?(\d+)$', rango.strip())
    if not m:
        raise ValueError('rango de origen no reconocido: %s' % rango)
    numero = lambda letras: sum((ord(c) - 64) * 26 ** i for i, c in enumerate(reversed(letras)))
    return {'min_col': numero(m.group(1)), 'min_row': int(m.group(2)),
            'max_col': numero(m.group(3)), 'max_row': int(m.group(4))}


def completar(entrada, salida):
    """Escribe en `salida` el libro con los registros de cada caché que no los
    tenga. Devuelve {caché: registros escritos} (vacío: nada que hacer)."""
    import openpyxl
    with zipfile.ZipFile(entrada) as z:
        nombres = z.namelist()
        cachés = [n for n in nombres if re.match(r'xl/pivotCache/pivotCacheDefinition\d+\.xml$', n)]
        if not cachés:
            return {}
        libro = None
        nuevas, informe = {}, {}
        for pieza in cachés:
            definicion = z.read(pieza).decode('utf-8')
            if re.search(r'<pivotCacheDefinition\b[^>]*\br:id="', definicion):
                continue                            # ya tiene registros
            origen = re.search(r'<worksheetSource\b([^>]*)/>', definicion)
            if not origen or not _atributo(origen.group(1), 'ref') or not _atributo(origen.group(1), 'sheet'):
                continue                            # origen con nombre definido o externo: no se calcula
            if libro is None:
                libro = openpyxl.load_workbook(entrada, read_only=True, data_only=True)
            filas = _filas_del_origen(libro, _desescapar(_atributo(origen.group(1), 'sheet')),
                                      _atributo(origen.group(1), 'ref'))
            if filas is None:
                continue
            xml, cuantos = registros(definicion, filas)
            numero = re.search(r'(\d+)\.xml$', pieza).group(1)
            destino = 'xl/pivotCache/pivotCacheRecords%s.xml' % numero
            rels = 'xl/pivotCache/_rels/pivotCacheDefinition%s.xml.rels' % numero
            texto_rels = z.read(rels).decode('utf-8') if rels in nombres else (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>')
            # Google deja una relación vacía «externalLinkPath» sin destino: el editor no la necesita.
            texto_rels = re.sub(r'<Relationship\b(?![^>]*\bTarget=)[^>]*/>', '', texto_rels)
            identificador = 'rIdRegistros%s' % numero
            texto_rels = texto_rels.replace('</Relationships>', '<Relationship Id="%s" Type="%s" Target="%s"/>'
                                            '</Relationships>' % (identificador, _TIPO_REGISTROS,
                                                                  posixpath.basename(destino)))
            definicion = re.sub(r'<pivotCacheDefinition\b', '<pivotCacheDefinition r:id="%s" recordCount="%d"'
                                % (identificador, cuantos), definicion, count=1)
            definicion = definicion.replace(' invalid="1"', '', 1)
            if 'refreshOnLoad=' not in definicion:
                definicion = definicion.replace('<pivotCacheDefinition ', '<pivotCacheDefinition refreshOnLoad="1" ', 1)
            nuevas[pieza] = definicion
            nuevas[rels] = texto_rels
            nuevas[destino] = xml
            informe[pieza] = cuantos
        if not informe:
            return {}
        tipos = z.read('[Content_Types].xml').decode('utf-8')
        for destino in [n for n in nuevas if 'pivotCacheRecords' in n]:
            if destino not in tipos:
                tipos = tipos.replace('</Types>', '<Override PartName="/%s" ContentType="%s"/></Types>'
                                      % (destino, _CONTENIDO_REGISTROS))
        nuevas['[Content_Types].xml'] = tipos
        with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as destino_zip:
            for info in z.infolist():
                if info.filename in nuevas:
                    destino_zip.writestr(info, nuevas.pop(info.filename).encode('utf-8'))
                else:
                    destino_zip.writestr(info, z.read(info.filename))
            for nombre, texto in nuevas.items():         # piezas nuevas (registros, rels)
                destino_zip.writestr(nombre, texto.encode('utf-8'))
    return informe


def hojas_por_nombre(z):
    """{nombre de la hoja: pieza del ZIP}."""
    libro = z.read('xl/workbook.xml').decode('utf-8', 'replace')
    rels = z.read('xl/_rels/workbook.xml.rels').decode('utf-8', 'replace')
    destino = {m.group(1): m.group(2) for m in re.finditer(r'Id="(rId\d+)"[^>]*?Target="([^"]*)"', rels)}
    salida = {}
    for m in re.finditer(r'<sheet\b([^>]*)/>', libro):
        nombre, rid = _atributo(m.group(1), 'name'), _atributo(m.group(1), 'r:id')
        if nombre and rid in destino:
            salida[_desescapar(nombre)] = posixpath.normpath('xl/' + destino[rid].lstrip('/'))
    return salida


def ubicaciones(z):
    """{hoja: [rango de cada tabla dinámica]} (el `location ref` de cada pivotTable)."""
    salida = {}
    for hoja, pieza in hojas_por_nombre(z).items():
        carpeta, nombre = posixpath.split(pieza)
        rels = posixpath.join(carpeta, '_rels', nombre + '.rels')
        if rels not in z.namelist():
            continue
        for destino in re.findall(r'Target="([^"]*pivotTable\d+\.xml)"', z.read(rels).decode('utf-8')):
            tabla = z.read(posixpath.normpath(posixpath.join(carpeta, destino))).decode('utf-8')
            lugar = re.search(r'<location\b[^>]*\bref="([^"]+)"', tabla)
            if lugar:
                salida.setdefault(hoja, []).append(lugar.group(1))
    return salida


def arreglar(entrada, salida, resultados=None):
    """Registros de la caché y, si se dan, el resultado de Google en las celdas.
    Devuelve el informe (vacío si no había nada que hacer)."""
    import tablas_dinamicas_resultado
    informe = completar(entrada, salida)
    actual = salida if informe else entrada
    if resultados:
        temporal = salida + '.celdas'
        with zipfile.ZipFile(actual) as z:
            hojas = hojas_por_nombre(z)
        escritas = tablas_dinamicas_resultado.escribir(actual, temporal, resultados, hojas)
        if escritas:
            os.replace(temporal, salida)
            informe['celdas del resultado'] = escritas
        elif os.path.exists(temporal):
            os.unlink(temporal)
    if informe and actual == entrada and not os.path.exists(salida):
        shutil.copyfile(entrada, salida)
    return informe


if __name__ == '__main__':
    argumentos = sys.argv[1:]
    resultados = None
    if '--resultados' in argumentos:
        posicion = argumentos.index('--resultados')
        try:
            with open(argumentos[posicion + 1], encoding='utf-8') as archivo:
                resultados = json.load(archivo)
        except (IndexError, OSError, ValueError):
            resultados = None
        del argumentos[posicion:posicion + 2]
    if len(argumentos) < 2:
        print(__doc__)
        sys.exit(2)
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    resultado = arreglar(argumentos[0], argumentos[1], resultados)
    print(resultado or 'No hacía falta nada.')
    sys.exit(0 if resultado else 1)
