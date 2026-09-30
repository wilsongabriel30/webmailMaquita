# -*- coding: utf-8 -*-
"""
Formularios del Almacén — añadir filas a la tabla «Respuestas» tocando solo el XML
=================================================================================
Reescribir el libro con openpyxl (cargar y guardar) estropeaba las fórmulas para
OnlyOffice: `=SUM(Respuestas[[#This Row],[…]])` salía como TEXTO en vez de
calcularse (comprobado con ConvertService el 17/09/2026: el original daba 10,
la copia de openpyxl «=SUM(…»). También cambia estilos, cadenas compartidas y
metadatos que la persona no tocó.

Por eso aquí el `.xlsx` se trata como lo que es, un zip de XML:

- Se copian **byte a byte** todas las partes del archivo, salvo tres: la hoja
  de la tabla «Respuestas» (se añaden filas y, si hace falta, encabezados),
  la definición de la tabla (su rango y columnas) y `workbook.xml` (se pide
  recalcular al abrir).
- Las filas nuevas toman el estilo de la fila de arriba. Las columnas que no
  son de ninguna pregunta copian la fórmula de arriba, ajustada a la fila.

Autoría: Equipo de Tecnología Maquita — 2026-09-17
"""
import io
import posixpath
import re
import zipfile
from datetime import datetime
from html import unescape as _desescapar
from xml.sax.saxutils import escape


def unescape(texto, _entidades=None):
    """Texto de XML a texto normal. openpyxl escribe las tildes como referencias
    numéricas («&#233;»), que `saxutils.unescape` deja sin traducir: los
    encabezados con tilde no se reconocían y se duplicaban (17/09/2026)."""
    return _desescapar(texto or '')

RE_CELDA = re.compile(r'<c r="([A-Z]+)(\d+)"([^>]*?)(?:/>|>(.*?)</c>)', re.S)
RE_FILA = re.compile(r'<row r="(\d+)"([^>]*?)(?:/>|>(.*?)</row>)', re.S)


class SinTabla(Exception):
    """El libro no tiene la tabla «Respuestas»."""


# ── lectura del paquete ──────────────────────────────────────────────────
def _rels(z, parte):
    carpeta, nombre = posixpath.split(parte)
    ruta = posixpath.join(carpeta, '_rels', nombre + '.rels')
    if ruta not in z.namelist():
        return {}
    xml = z.read(ruta).decode('utf-8')
    salida = {}
    for rel in re.findall(r'<Relationship\b[^>]*>', xml):
        id_ = re.search(r'Id="([^"]+)"', rel)
        destino = re.search(r'Target="([^"]+)"', rel)
        if id_ and destino:
            objetivo = destino.group(1)
            objetivo = (objetivo.lstrip('/') if objetivo.startswith('/')
                        else posixpath.normpath(posixpath.join(carpeta, objetivo)))
            salida[id_.group(1)] = objetivo
    return salida


def _buscar_tabla(z):
    """(parte_hoja, parte_tabla) de la tabla «Respuestas»."""
    for parte in z.namelist():
        if not re.fullmatch(r'xl/worksheets/[^/]+\.xml', parte):
            continue
        for objetivo in _rels(z, parte).values():
            if '/tables/' in objetivo and objetivo in z.namelist():
                xml = z.read(objetivo).decode('utf-8')
                if re.search(r'\bdisplayName="Respuestas"', xml):
                    return parte, objetivo
    raise SinTabla()


def _cadenas(z):
    if 'xl/sharedStrings.xml' not in z.namelist():
        return []
    xml = z.read('xl/sharedStrings.xml').decode('utf-8')
    return [unescape(''.join(re.findall(r'<t[^>]*>(.*?)</t>', si, re.S)))
            for si in re.findall(r'<si>(.*?)</si>', xml, re.S)]


def _texto_celda(atributos, interior, cadenas):
    interior = interior or ''
    if 't="s"' in atributos:
        v = re.search(r'<v>(\d+)</v>', interior)
        return cadenas[int(v.group(1))] if v and int(v.group(1)) < len(cadenas) else ''
    if 't="inlineStr"' in atributos:
        return unescape(''.join(re.findall(r'<t[^>]*>(.*?)</t>', interior, re.S)))
    v = re.search(r'<v>(.*?)</v>', interior, re.S)
    return unescape(v.group(1)) if v else ''


def _col_num(letras):
    n = 0
    for ch in letras:
        n = n * 26 + ord(ch) - 64
    return n


def _col_letras(n):
    s = ''
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _rango(ref):
    m = re.fullmatch(r'([A-Z]+)(\d+):([A-Z]+)(\d+)', ref)
    return _col_num(m.group(1)), int(m.group(2)), _col_num(m.group(3)), int(m.group(4))


# ── API ──────────────────────────────────────────────────────────────────
def leer_encabezados(contenido):
    """Encabezados de la tabla «Respuestas» (lista de textos)."""
    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        parte_hoja, parte_tabla = _buscar_tabla(z)
        c1, f1, c2, _ = _rango(re.search(r'\bref="([^"]+)"',
                                         z.read(parte_tabla).decode('utf-8')).group(1))
        filas = _filas(z.read(parte_hoja).decode('utf-8'))
        cadenas = _cadenas(z)
        celdas = filas.get(f1, {}).get('celdas', {})
        return [_texto_celda(celdas[c][1], celdas[c][2], cadenas) if c in celdas else ''
                for c in range(c1, c2 + 1)]


def leer_tabla(contenido):
    """(encabezados, filas) de la tabla «Respuestas»: textos tal como están
    guardados (los números y fechas, como número en texto). Solo filas con algo."""
    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        parte_hoja, parte_tabla = _buscar_tabla(z)
        c1, f1, c2, _ = _rango(re.search(r'\bref="([^"]+)"',
                                         z.read(parte_tabla).decode('utf-8')).group(1))
        filas = _filas(z.read(parte_hoja).decode('utf-8'))
        cadenas = _cadenas(z)

        def textos(n):
            celdas = filas.get(n, {}).get('celdas', {})
            return [_texto_celda(celdas[c][1], celdas[c][2], cadenas) if c in celdas else ''
                    for c in range(c1, c2 + 1)]
        cuerpo = [textos(n) for n in sorted(filas) if n > f1]
        return textos(f1), [f for f in cuerpo if any(v != '' for v in f)]


def _filas(xml_hoja):
    datos = re.search(r'<sheetData[^>]*?(?:/>|>(.*?)</sheetData>)', xml_hoja, re.S)
    filas = {}
    for m in RE_FILA.finditer((datos.group(1) or '') if datos else ''):
        celdas = {}
        for c in RE_CELDA.finditer(m.group(3) or ''):
            celdas[_col_num(c.group(1))] = (c.group(0), c.group(3), c.group(4))
        filas[int(m.group(1))] = {'atributos': m.group(2), 'celdas': celdas}
    return filas


def _tupla(xml_celda):
    """(xml, atributos, interior) de una celda generada, como las leídas."""
    m = RE_CELDA.fullmatch(xml_celda)
    return (xml_celda, m.group(3), m.group(4)) if m else (xml_celda, '', '')


def _ref_estructurada(titulo):
    """Un encabezado tal como se escribe dentro de Tabla[[…],[título]]."""
    return re.sub(r"([\[\]#'])", r"'\1", titulo)


def _renombrar_en_formulas(xml, viejo, nuevo):
    a = '[' + _ref_estructurada(viejo) + ']'
    b = '[' + _ref_estructurada(nuevo) + ']'

    def cambia(m):
        texto = unescape(m.group(3))
        if a not in texto:
            return m.group(0)
        return '<%s%s>%s</%s>' % (m.group(1), m.group(2), escape(texto.replace(a, b)), m.group(1))
    return re.sub(r'<(f|calculatedColumnFormula|totalsRowFormula)\b([^>]*)>(.*?)</\1>',
                  cambia, xml, flags=re.S)


def _renombrar_columna_tabla(xml_tabla, viejo, nuevo):
    def cambia(m):
        if unescape(m.group(2), {'&quot;': '"'}) != viejo:
            return m.group(0)
        return m.group(1) + escape(nuevo, {'"': '&quot;'}) + m.group(3)
    return re.sub(r'(<tableColumn\b[^>]*?\bname=")([^"]*)(")', cambia, xml_tabla)


def _celda_valor(coord, estilo, valor):
    s = ' s="%s"' % estilo if estilo else ''
    if valor is None or valor == '':
        return '<c r="%s"%s/>' % (coord, s)
    if isinstance(valor, datetime):
        serial = (valor - datetime(1899, 12, 30)).total_seconds() / 86400.0
        return '<c r="%s"%s><v>%s</v></c>' % (coord, s, repr(round(serial, 8)))
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return '<c r="%s"%s><v>%s</v></c>' % (coord, s, valor)
    return ('<c r="%s"%s t="inlineStr"><is><t xml:space="preserve">%s</t></is></c>'
            % (coord, s, escape(str(valor))))


def _formula_trasladada(filas, col, fila_origen, coord_destino):
    """Fórmula de la celda de arriba adaptada a la nueva fila, o None."""
    celda = filas.get(fila_origen, {}).get('celdas', {}).get(col)
    if not celda:
        return None
    f = re.search(r'<f([^>]*)(?:/>|>(.*?)</f>)', celda[2] or '', re.S)
    if not f:
        return None
    texto, origen = unescape(f.group(2) or ''), '%s%d' % (_col_letras(col), fila_origen)
    si = re.search(r'\bsi="(\d+)"', f.group(1))
    if not texto and si:                       # fórmula compartida: buscar la maestra
        for n, fila in filas.items():
            for c, (_, _, interior) in fila['celdas'].items():
                m = re.search(r'<f[^>]*\bsi="%s"[^>]*\bref="[^"]+"[^>]*>(.*?)</f>' % si.group(1),
                              interior or '', re.S)
                if m and m.group(1):
                    texto, origen = unescape(m.group(1)), '%s%d' % (_col_letras(c), n)
    if not texto:
        return None
    try:
        from openpyxl.formula.translate import Translator
        return Translator('=' + texto, origin=origen).translate_formula(coord_destino)[1:]
    except Exception:
        return texto


def anadir_filas(contenido, filas_nuevas, columnas_nuevas=(), renombres=(), destino=None):
    """Devuelve el `.xlsx` (bytes) con las filas añadidas al final de la tabla.

    `filas_nuevas`: listas de valores alineadas con las columnas de la tabla
    (None = columna sin dato → fórmula de la fila de arriba si la hay).
    `columnas_nuevas`: títulos a añadir como columnas al final de la tabla
    (van ANTES que las filas: `filas_nuevas` ya las incluye al final).
    `renombres`: pares (encabezado actual, encabezado nuevo): cambia el
    encabezado, la columna de la tabla y las fórmulas que la nombran.
    `destino` (28/09/2026, «Recibir respuestas de un formulario»): escribir en
    otra tabla u otro rango que no sea la tabla «Respuestas». Es lo que devuelve
    `formulario_destinos_xml.localizar`: {parte_hoja, parte_tabla (o None si la
    hoja no tiene tabla), c1, f1, c2, f2, columnas_clave}. `columnas_clave` son
    las columnas que llenan las respuestas: la última fila con datos se busca
    SOLO en ellas, porque la persona suele dejar filas preparadas con fórmulas.
    """
    zin = zipfile.ZipFile(io.BytesIO(contenido))
    if destino:
        parte_hoja, parte_tabla = destino['parte_hoja'], destino.get('parte_tabla')
    else:
        parte_hoja, parte_tabla = _buscar_tabla(zin)
    xml_hoja = zin.read(parte_hoja).decode('utf-8')
    xml_tabla = zin.read(parte_tabla).decode('utf-8') if parte_tabla else ''
    if destino:
        c1, f1, c2, f2 = destino['c1'], destino['f1'], destino['c2'], destino['f2']
    else:
        c1, f1, c2, f2 = _rango(re.search(r'\bref="([^"]+)"', xml_tabla).group(1))
    claves = set((destino or {}).get('columnas_clave') or range(c1, c2 + 1))
    filas = _filas(xml_hoja)

    cab = filas.setdefault(f1, {'atributos': '', 'celdas': {}})
    cadenas = _cadenas(zin)
    hechos = []
    for viejo, nuevo in renombres:
        for col in range(c1, c2 + 1):
            celda = cab['celdas'].get(col)
            if celda and _texto_celda(celda[1], celda[2], cadenas) == viejo:
                estilo = re.search(r'\bs="(\d+)"', celda[1] or '')
                cab['celdas'][col] = _tupla(_celda_valor(
                    '%s%d' % (_col_letras(col), f1), estilo.group(1) if estilo else None, nuevo))
                xml_tabla = _renombrar_columna_tabla(xml_tabla, viejo, nuevo)
                xml_tabla = _renombrar_en_formulas(xml_tabla, viejo, nuevo)
                hechos.append((viejo, nuevo))
                break

    # Última fila con contenido dentro de las columnas de la tabla (se calcula
    # antes de tocar columnas: hace falta para saber qué columnas están en uso).
    ultima = f1
    for n, fila in filas.items():
        if n > f1 and any(c1 <= c <= c2 and c in claves and (interior or '').strip()
                          for c, (_, _, interior) in fila['celdas'].items()):
            ultima = max(ultima, n)

    def _ocupada(columna):
        """¿Hay algo en esa columna? Encabezado o cualquier celda con contenido.

        Es lo que impide escribir encima de una columna de la persona pegada a
        la derecha de la tabla: la de «TOTAL» de las hojas de provincia, sin ir
        más lejos. Pisarla borraba su fórmula y su título (22/09/2026).
        """
        celda = cab['celdas'].get(columna)
        if celda and _texto_celda(celda[1], celda[2], cadenas).strip():
            return True
        for n, fila in filas.items():
            if n <= f1 or n > ultima:
                continue
            otra = fila['celdas'].get(columna)
            if otra and (otra[2] or '').strip():
                return True
        return False

    def _apuntar_columna(numero, titulo):
        ids = [int(x) for x in re.findall(r'<tableColumn\b[^>]*\bid="(\d+)"', xml_tabla)] or [0]
        return xml_tabla.replace(
            '</tableColumns>', '<tableColumn id="%d" name="%s"/></tableColumns>'
            % (max(ids) + 1, escape(titulo, {'"': '&quot;'})))

    # Estilo de encabezado para columnas nuevas: el de la última columna.
    estilo_cab = re.search(r'\bs="(\d+)"', (cab['celdas'].get(c2) or ('', '', ''))[1] or '')
    usados = set()
    for columna in range(c1, c2 + 1):
        celda = cab['celdas'].get(columna)
        if celda:
            usados.add(_texto_celda(celda[1], celda[2], cadenas).strip().upper())
    for titulo in columnas_nuevas:
        # Lo que ya tiene contenido es de la persona: la tabla se estira hasta
        # pasarlo y esas columnas entran con el nombre que ya tienen.
        while _ocupada(c2 + 1):
            c2 += 1
            celda = cab['celdas'].get(c2)
            propio = _texto_celda(celda[1], celda[2], cadenas).strip() if celda else ''
            n = 1
            while not propio or propio.upper() in usados:
                n += 1
                propio = (propio or 'Columna') + ' (%d)' % n if propio else 'Columna %d' % n
            usados.add(propio.upper())
            if not celda:
                cab['celdas'][c2] = _tupla(_celda_valor(
                    '%s%d' % (_col_letras(c2), f1),
                    estilo_cab.group(1) if estilo_cab else None, propio))
            xml_tabla = _apuntar_columna(c2, propio)
        c2 += 1
        coord = '%s%d' % (_col_letras(c2), f1)
        xml_c = _celda_valor(coord, estilo_cab.group(1) if estilo_cab else None, titulo)
        cab['celdas'][c2] = _tupla(xml_c)
        usados.add(titulo.strip().upper())
        xml_tabla = _apuntar_columna(c2, titulo)

    for valores in filas_nuevas:
        arriba, ultima = ultima, ultima + 1
        fila = filas.setdefault(ultima, {'atributos': '', 'celdas': {}})
        plantilla = filas.get(arriba, {}).get('celdas', {}) if arriba > f1 else {}
        for i, col in enumerate(range(c1, c2 + 1)):
            coord = '%s%d' % (_col_letras(col), ultima)
            estilo = re.search(r'\bs="(\d+)"', (plantilla.get(col) or ('', '', ''))[1] or '')
            estilo = estilo.group(1) if estilo else None
            valor = valores[i] if i < len(valores) else None
            if valor is None and arriba > f1:
                formula = _formula_trasladada(filas, col, arriba, coord)
                if formula:
                    s = ' s="%s"' % estilo if estilo else ''
                    fila['celdas'][col] = _tupla('<c r="%s"%s><f>%s</f></c>'
                                                 % (coord, s, escape(formula)))
                    continue
            fila['celdas'][col] = _tupla(_celda_valor(coord, estilo, valor))
        if arriba > f1 and not fila['atributos'].strip():
            alto = re.search(r'\s(ht="[^"]+"\s+customHeight="1")', filas[arriba]['atributos'])
            fila['atributos'] = (' ' + alto.group(1)) if alto else ''

    # sheetData reconstruido en orden (las filas que no se tocaron, tal cual).
    def xml_fila(n, fila):
        celdas = ''.join(fila['celdas'][c][0] for c in sorted(fila['celdas']))
        atributos = re.sub(r'\sspans="[^"]*"', '', fila['atributos'])
        return '<row r="%d"%s>%s</row>' % (n, atributos, celdas) if celdas else \
               '<row r="%d"%s/>' % (n, atributos)
    datos = ''.join(xml_fila(n, filas[n]) for n in sorted(filas))
    xml_hoja = re.sub(r'<sheetData[^>]*?(?:/>|>.*?</sheetData>)',
                      lambda _: '<sheetData>%s</sheetData>' % datos, xml_hoja, count=1, flags=re.S)

    nueva_ref = '%s%d:%s%d' % (_col_letras(c1), f1, _col_letras(c2), max(ultima, f2))
    xml_tabla = re.sub(r'(<table\b[^>]*?\bref=")[^"]+(")', r'\g<1>%s\2' % nueva_ref, xml_tabla, count=1)
    xml_tabla = re.sub(r'(<autoFilter\b[^>]*?\bref=")[^"]+(")', r'\g<1>%s\2' % nueva_ref, xml_tabla, count=1)
    xml_tabla = re.sub(r'(<tableColumns\b[^>]*?\bcount=")\d+(")',
                       lambda m: '%s%d%s' % (m.group(1), c2 - c1 + 1, m.group(2)), xml_tabla, count=1)
    dimension = re.search(r'<dimension ref="([^"]+)"', xml_hoja)
    if dimension and ':' in dimension.group(1):
        d1, e1, d2, e2 = _rango(dimension.group(1))
        xml_hoja = xml_hoja.replace(dimension.group(0), '<dimension ref="%s%d:%s%d"' % (
            _col_letras(min(d1, c1)), min(e1, f1), _col_letras(max(d2, c2)), max(e2, ultima)), 1)

    xml_libro = zin.read('xl/workbook.xml').decode('utf-8')
    if '<calcPr' in xml_libro:
        if 'fullCalcOnLoad' not in xml_libro:
            xml_libro = xml_libro.replace('<calcPr', '<calcPr fullCalcOnLoad="1"', 1)
    else:
        ancla = '<extLst' if '<extLst' in xml_libro else '</workbook>'
        xml_libro = xml_libro.replace(ancla, '<calcPr fullCalcOnLoad="1"/>' + ancla, 1)

    cambiadas = {parte_hoja: xml_hoja, 'xl/workbook.xml': xml_libro}
    if parte_tabla:
        cambiadas[parte_tabla] = xml_tabla
    if hechos:                      # las fórmulas de TODAS las pestañas siguen a la columna
        for parte in zin.namelist():
            if re.fullmatch(r'xl/worksheets/[^/]+\.xml', parte):
                xml = cambiadas.get(parte) or zin.read(parte).decode('utf-8')
                nuevo_xml = xml
                for viejo, nuevo in hechos:
                    nuevo_xml = _renombrar_en_formulas(nuevo_xml, viejo, nuevo)
                if nuevo_xml != xml or parte in cambiadas:
                    cambiadas[parte] = nuevo_xml
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            if info.filename in cambiadas:
                zout.writestr(info, cambiadas[info.filename].encode('utf-8'))
            else:
                zout.writestr(info, zin.read(info.filename))
    return salida.getvalue()
