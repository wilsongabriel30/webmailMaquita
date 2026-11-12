# -*- coding: utf-8 -*-
"""El resultado de las tablas dinámicas de Google, escrito en sus celdas (20/10/2026).

Google exporta la tabla dinámica sin las celdas del resultado, y el editor del
Drive no la calcula al abrir (solo con «Actualizar», que es una edición). La
exportación HTML del libro sí trae ese resultado tal como lo enseña Google:

    <td class="s3">Recuperable</td><td class="s3"></td><td class="s4">$13.248,95</td>

`leer(zip_html, ubicaciones)` saca, para el rango de cada tabla, el texto de
cada celda y su estilo (negrita, fondo); `escribir(xlsx, salida, resultados)`
lo pone en las celdas vacías (nunca pisa una celda que ya exista): los números como números (con el formato que se ve:
«$13.248,95» → 13248.95 con "$"#,##0.00), lo demás como texto. Con los
registros de la caché (tablas_dinamicas.py) la tabla además se puede
actualizar y filtrar en el Drive. Solo biblioteca estándar.
"""
import html
import re
import zipfile
from xml.sax.saxutils import escape

_FILA = re.compile(r'<tr[^>]*>(.*?)</tr>', re.S)
_CELDA = re.compile(r'<td\b([^>]*)>(.*?)</td>', re.S)
_NUMERO = re.compile(r'^(-?)(\$?)\s*(-?)([\d.]+(?:,\d+)?)\s*(%?)$')


def _columna(letras):
    numero = 0
    for letra in letras:
        numero = numero * 26 + ord(letra) - 64
    return numero


def _letras(numero):
    texto = ''
    while numero:
        numero, resto = divmod(numero - 1, 26)
        texto = chr(65 + resto) + texto
    return texto


def _rango(ref):
    m = re.match(r'([A-Z]+)(\d+):([A-Z]+)(\d+)$', ref.replace('$', ''))
    if not m:
        m = re.match(r'([A-Z]+)(\d+)$', ref.replace('$', ''))
        return (_columna(m.group(1)), int(m.group(2)), _columna(m.group(1)), int(m.group(2))) if m else None
    return _columna(m.group(1)), int(m.group(2)), _columna(m.group(3)), int(m.group(4))


def _estilos_css(texto):
    """{clase: {'negrita': bool, 'fondo': 'RRGGBB' o None}} del <style> de la hoja."""
    salida = {}
    for m in re.finditer(r'\.ritz \.waffle \.(s\d+)\{([^}]*)\}', texto):
        reglas = m.group(2)
        fondo = re.search(r'background-color:#([0-9a-fA-F]{6})', reglas)
        letra = re.search(r'(?<![-\w])color:#([0-9a-fA-F]{6})', reglas)
        salida[m.group(1)] = {'negrita': bool(re.search(r'font-weight:bold', reglas)),
                              'fondo': fondo.group(1).upper() if fondo and fondo.group(1).lower() != 'ffffff' else None,
                              'color': letra.group(1).upper() if letra and letra.group(1).lower() != '000000' else None}
    return salida


def _texto(celda):
    return html.unescape(re.sub(r'<[^>]+>', '', celda)).replace('\xa0', ' ').strip()


def tabla_de_hoja(texto):
    """[[ (texto, clase) por columna ] por fila ] de la cuadrícula de una hoja HTML."""
    tabla = re.search(r'<table class="waffle[^"]*".*?</table>', texto, re.S)
    if not tabla:
        return []
    filas = []
    for fila in _FILA.findall(tabla.group(0))[1:]:           # la primera: letras de columna
        celdas = []
        for m in _CELDA.finditer(fila):
            clase = re.search(r'class="(s\d+)', m.group(1))
            union = re.search(r'colspan="(\d+)"', m.group(1))
            celdas.append((_texto(m.group(2)), clase.group(1) if clase else None))
            celdas.extend([('', None)] * (int(union.group(1)) - 1 if union else 0))
        filas.append(celdas)
    return filas


def leer(zip_html, ubicaciones):
    """{hoja: [ {celda, texto, negrita, fondo} ]} de los rangos de `ubicaciones`
    ({hoja: [ref, …]}) en la exportación HTML."""
    salida = {}
    with zipfile.ZipFile(zip_html) as z:
        nombres = {n[:-5]: n for n in z.namelist() if '/' not in n and n.endswith('.html')}
        for hoja, rangos in ubicaciones.items():
            simple = lambda t: re.sub(r'\W+', '', t).lower()
            pieza = next((n for clave, n in nombres.items() if simple(clave) == simple(hoja)), None)
            if not pieza:
                continue
            texto = z.read(pieza).decode('utf-8', 'replace')
            css, filas = _estilos_css(texto), tabla_de_hoja(texto)
            celdas = []
            for ref in rangos:
                limites = _rango(ref)
                if not limites:
                    continue
                c1, f1, c2, f2 = limites
                for fila in range(f1, f2 + 1):
                    for col in range(c1, c2 + 1):
                        if fila - 1 >= len(filas) or col - 1 >= len(filas[fila - 1]):
                            continue
                        contenido, clase = filas[fila - 1][col - 1]
                        estilo = css.get(clase, {})
                        celdas.append({'celda': '%s%d' % (_letras(col), fila), 'texto': contenido,
                                       'negrita': estilo.get('negrita', False), 'fondo': estilo.get('fondo'),
                                       'color': estilo.get('color')})
            salida[hoja] = celdas
    return salida


def numero(texto):
    """«$13.248,95» → (13248.95, '"$"#,##0.00'); «16,4%» → (0.164, '0.0%'); texto → (None, None)."""
    m = _NUMERO.match(texto.replace(' ', ''))
    if not m or (m.group(4).count(',') > 1):
        return None, None
    cifra = m.group(4)
    if '.' in cifra and ',' not in cifra and not re.match(r'^\d{1,3}(\.\d{3})+$', cifra):
        return None, None                                    # «1.5» no es una cifra de es-EC
    entero, _, decimales = cifra.partition(',')
    valor = float(entero.replace('.', '') + ('.' + decimales if decimales else ''))
    if m.group(1) or m.group(3):
        valor = -valor
    patron = '#,##0' + ('.' + '0' * len(decimales) if decimales else '')
    if m.group(5):
        return round(valor / 100, 12), ('0' + ('.' + '0' * len(decimales) if decimales else '') + '%')
    return valor, ('"$"' + patron if m.group(2) else patron)


# ── estilos nuevos en styles.xml ─────────────────────────────────────────
class _Estilos:
    def __init__(self, xml):
        self.xml = xml
        self.cache = {}

    def _anadir(self, seccion, elemento):
        m = re.search(r'(<%s\b[^>]*count=")(\d+)("[^>]*>)(.*?)(</%s>)' % (seccion, seccion), self.xml, re.S)
        if not m:
            raise ValueError('styles.xml sin <%s>' % seccion)
        cuantos = int(m.group(2))
        self.xml = (self.xml[:m.start()] + m.group(1) + str(cuantos + 1) + m.group(3) + m.group(4) + elemento
                    + m.group(5) + self.xml[m.end():])
        return cuantos

    def indice(self, formato, negrita, fondo, color=None):
        clave = (formato, negrita, fondo, color)
        if clave in self.cache:
            return self.cache[clave]
        numero_formato = 0
        if formato:
            usados = [int(n) for n in re.findall(r'<numFmt numFmtId="(\d+)"', self.xml)]
            numero_formato = max(usados + [199]) + 1
            elemento = '<numFmt numFmtId="%d" formatCode="%s"/>' % (numero_formato, escape(formato, {'"': '&quot;'}))
            if '<numFmts' in self.xml:
                self._anadir('numFmts', elemento)
            else:
                self.xml = self.xml.replace('<fonts', '<numFmts count="1">%s</numFmts><fonts' % elemento, 1)
        fuente = (self._anadir('fonts', '<font>%s<sz val="10"/>%s<name val="Arial"/></font>'
                               % ('<b/>' if negrita else '', '<color rgb="FF%s"/>' % color if color else ''))
                  if (negrita or color) else 0)
        relleno = (self._anadir('fills', '<fill><patternFill patternType="solid"><fgColor rgb="FF%s"/>'
                                '<bgColor indexed="64"/></patternFill></fill>' % fondo) if fondo else 0)
        xf = ('<xf numFmtId="%d" fontId="%d" fillId="%d" borderId="0" xfId="0" applyNumberFormat="1" '
              'applyFont="1" applyFill="1"/>' % (numero_formato, fuente, relleno))
        self.cache[clave] = self._anadir('cellXfs', xf)
        return self.cache[clave]


def _celda_xml(celda, estilos):
    valor, formato = numero(celda['texto'])
    s = estilos.indice(formato, celda['negrita'], celda['fondo'], celda.get('color'))
    if valor is not None:
        return '<c r="%s" s="%d"><v>%s</v></c>' % (celda['celda'], s, repr(valor))
    if not celda['texto']:
        return '<c r="%s" s="%d"/>' % (celda['celda'], s) if (celda['negrita'] or celda['fondo']) else ''
    return '<c r="%s" s="%d" t="inlineStr"><is><t xml:space="preserve">%s</t></is></c>' % (
        celda['celda'], s, escape(celda['texto']))


def _poner_celdas(hoja_xml, nuevas):
    """Mezcla las celdas nuevas ({ref: xml}) en <sheetData>, en orden de fila y columna."""
    datos = re.search(r'<sheetData\s*/>|<sheetData>(.*?)</sheetData>', hoja_xml, re.S)
    filas = {}
    for fila in re.finditer(r'<row\b([^>]*?)(?:/>|>(.*?)</row>)', datos.group(1) or '', re.S):
        numero_fila = int(re.search(r'\br="(\d+)"', fila.group(1)).group(1))
        celdas = {m.group(1): m.group(0) for m in re.finditer(
            r'<c r="([A-Z]+\d+)"[^>]*?(?:/>|>.*?</c>)', fila.group(2) or '', re.S)}
        filas[numero_fila] = [re.sub(r'\s*spans="[^"]*"', '', fila.group(1)), celdas]
    for ref, xml in nuevas.items():
        numero_fila = int(re.search(r'\d+', ref).group(0))
        filas.setdefault(numero_fila, [' r="%d"' % numero_fila, {}])[1][ref] = xml
    orden = lambda ref: _columna(re.match(r'[A-Z]+', ref).group(0))
    cuerpo = ''.join('<row%s>%s</row>' % (filas[n][0], ''.join(filas[n][1][r] for r in sorted(filas[n][1], key=orden)))
                     for n in sorted(filas))
    hoja_xml = hoja_xml[:datos.start()] + '<sheetData>%s</sheetData>' % cuerpo + hoja_xml[datos.end():]
    todas = [r for n in filas for r in filas[n][1]]
    if todas:
        cols = [orden(r) for r in todas]
        nums = [int(re.search(r'\d+', r).group(0)) for r in todas]
        dimension = 'A1:%s%d' % (_letras(max(cols)), max(nums))
        hoja_xml = re.sub(r'<dimension ref="[^"]*"/>', '<dimension ref="%s"/>' % dimension, hoja_xml, count=1)
    return hoja_xml


def escribir(entrada, salida, resultados, hojas):
    """Pone los resultados ({hoja: celdas}, de `leer`) en las hojas (`hojas`:
    {nombre: pieza del ZIP}) — solo en celdas vacías del libro. Devuelve cuántas escribió."""
    with zipfile.ZipFile(entrada) as z:
        estilos = _Estilos(z.read('xl/styles.xml').decode('utf-8'))
        nuevas_piezas, total = {}, 0
        for hoja, celdas in resultados.items():
            pieza = hojas.get(hoja)
            if not pieza:
                continue
            texto = z.read(pieza).decode('utf-8')
            ocupadas = set(re.findall(r'<c r="([A-Z]+\d+)"', texto))      # nunca se pisa una celda del libro
            nuevas = {}
            for celda in celdas:
                if celda['celda'] in ocupadas:
                    continue
                xml = _celda_xml(celda, estilos)
                if xml:
                    nuevas[celda['celda']] = xml
            if nuevas:
                nuevas_piezas[pieza] = _poner_celdas(texto, nuevas)
                total += len(nuevas)
        if not total:
            return 0
        nuevas_piezas['xl/styles.xml'] = estilos.xml
        with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as destino:
            for info in z.infolist():
                datos = nuevas_piezas.get(info.filename)
                destino.writestr(info, datos.encode('utf-8') if datos is not None else z.read(info.filename))
    return total
