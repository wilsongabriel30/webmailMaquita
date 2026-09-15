"""Arregla los libros .xlsx exportados de Google Sheets para que en el editor
del Drive (OnlyOffice) se vean IGUAL que en Google.

── Qué le pasa a un libro que viene de Google (visto el 07/09/2026) ──

1. **Las columnas salen más estrechas de lo que Google dibuja.** Google mide las
   letras con su propia tipografía («docs-Calibri», más estrecha) y escribe en el
   archivo un ancho que, leído por cualquier otro programa, queda un ~10 % corto.
   Comprobado en este libro: Google pinta la columna a 156 px y el archivo dice
   19,63 caracteres, que son 142 px.

2. **Con «ajustar texto», eso descuadra la hoja entera.** Al no caber, el texto
   de las cabeceras salta a dos líneas y la fila se hace el doble de alta. Como
   Google tampoco escribe la altura de las filas, cada fila crece por su cuenta y
   la tabla se desplaza: es el «se daña el formato» de la migración.

3. **Las etiquetas de los gráficos pierden el formato.** Google las deja en
   «General» enlazado al origen y el editor enseña 0,633333333 donde debería
   poner 63 %.

── Qué hace este arreglo ──

  · Ensancha las columnas el 10 % que Google se deja, para que el texto quepa
    igual que allí.
  · Le pone a cada fila la altura que de verdad necesita (una línea si el texto
    cabe, dos si no), en vez de dejar que cada programa la invente.
  · Pone en las etiquetas de los gráficos el formato de número de las celdas de
    donde salen.

No toca nada más: ni datos, ni fórmulas, ni colores, ni listas, ni los gráficos.

Uso:  python3 arreglar_xlsx_google.py entrada.xlsx salida.xlsx
"""
import math
import re
import sys
import zipfile

FIRMA = (b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
         b'<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/'
         b'extended-properties"><Application>Drive Maquita</Application>'
         b'<Company>Fundacion Maquita</Company></Properties>')

# Lo que Google se deja al escribir el ancho de columna.
ENSANCHE = 1.10

# De ancho de columna (en caracteres, como lo guarda Excel) a píxeles.
def a_pixeles(ancho):
    return ancho * 7.0 + 5.0


def de_pixeles(px):
    return max(1.0, (px - 5.0) / 7.0)


# Alto de una línea, en puntos, según el tamaño de la letra.
def alto_de_linea(puntos):
    return max(12.75, round(puntos * 1.30 + 2.5, 2))


def ancho_medio_de_letra(puntos):
    """Ancho aproximado de un carácter, en píxeles, para Calibri/Arial."""
    return puntos * 0.55 * 96.0 / 72.0


def piezas_de(estilos_xml, etiqueta, patron):
    bloque = re.search(r'<%s[^>]*>(.*?)</%s>' % (etiqueta, etiqueta), estilos_xml, re.S)
    return re.findall(patron, bloque.group(1), re.S) if bloque else []


def datos_de_estilos(estilos_xml):
    """Para cada estilo de celda: tamaño de letra, si ajusta el texto y su
       formato de número."""
    fuentes = piezas_de(estilos_xml, 'fonts', r'<font>.*?</font>|<font\s*/>')
    tam_fuente = []
    for f in fuentes:
        m = re.search(r'<sz val="([\d.]+)"', f)
        tam_fuente.append(float(m.group(1)) if m else 11.0)

    codigos = {0: 'General', 9: '0%', 10: '0.00%', 1: '0', 2: '0.00',
               3: '#,##0', 4: '#,##0.00', 49: '@'}
    for m in re.finditer(r'<numFmt numFmtId="(\d+)" formatCode="([^"]*)"', estilos_xml):
        codigos[int(m.group(1))] = m.group(2)

    xfs = piezas_de(estilos_xml, 'cellXfs', r'<xf\b.*?(?:/>|</xf>)')
    salida = []
    for x in xfs:
        m = re.search(r'fontId="(\d+)"', x)
        idf = int(m.group(1)) if m else 0
        f = re.search(r'numFmtId="(\d+)"', x)
        salida.append({
            'tamano': tam_fuente[idf] if idf < len(tam_fuente) else 11.0,
            'ajusta': 'wrapText="1"' in x,
            'formato': codigos.get(int(f.group(1)) if f else 0, 'General')
        })
    return salida


def ensanchar_columnas(hoja_xml):
    """Devuelve (xml nuevo, {columna: ancho en píxeles})."""
    anchos = {}

    def arregla(m):
        atributos = m.group(1)
        w = re.search(r'width="([\d.]+)"', atributos)
        if not w:
            return m.group(0)
        nuevo = round(float(w.group(1)) * ENSANCHE, 2)
        desde = int(re.search(r'min="(\d+)"', atributos).group(1))
        hasta = int(re.search(r'max="(\d+)"', atributos).group(1))
        for c in range(desde, min(hasta, desde + 200) + 1):
            anchos[c] = a_pixeles(nuevo)
        atributos = re.sub(r'width="[\d.]+"', 'width="%s"' % nuevo, atributos)
        if 'customWidth' not in atributos:
            atributos += ' customWidth="1"'
        return '<col%s/>' % atributos

    return re.sub(r'<col([^>]*)/>', arregla, hoja_xml), anchos


def columna_de(referencia):
    letras = re.match(r'([A-Z]+)', referencia or '')
    if not letras:
        return 1
    n = 0
    for c in letras.group(1):
        n = n * 26 + (ord(c) - 64)
    return n


def texto_de_celda(celda_xml, textos):
    m = re.search(r'<v>([^<]*)</v>', celda_xml)
    if not m:
        return ''
    if 't="s"' in celda_xml:
        i = int(m.group(1))
        return textos[i] if i < len(textos) else ''
    return m.group(1)


def poner_alturas(hoja_xml, estilos, textos, anchos, ancho_normal_px):
    """Le pone a cada fila la altura que necesita su contenido."""
    cambiadas = [0]

    def arregla(m):
        atributos, dentro = m.group(1), m.group(2)
        if 'ht=' in atributos:
            return m.group(0)
        alto = 0.0
        for celda in re.findall(r'<c\b[^>]*(?:/>|>.*?</c>)', dentro, re.S):
            s = re.search(r'\bs="(\d+)"', celda)
            estilo = estilos[int(s.group(1))] if s and int(s.group(1)) < len(estilos) else None
            tamano = estilo['tamano'] if estilo else 11.0
            lineas = 1
            texto = texto_de_celda(celda, textos)
            if texto and '\n' in texto:
                lineas = texto.count('\n') + 1
            elif estilo and estilo['ajusta'] and texto:
                ref = re.search(r'r="([A-Z]+\d+)"', celda)
                px = anchos.get(columna_de(ref.group(1)) if ref else 1, ancho_normal_px)
                cabe = max(1, int((px - 6) / ancho_medio_de_letra(tamano)))
                lineas = max(1, math.ceil(len(texto) / float(cabe)))
            alto = max(alto, alto_de_linea(tamano) * lineas)
        if alto <= 0:
            alto = 15.0
        cambiadas[0] += 1
        return '<row%s ht="%s" customHeight="1">%s</row>' % (
            atributos, round(alto, 2), dentro)

    salida = re.sub(r'<row([^>]*)>(.*?)</row>', arregla, hoja_xml, flags=re.S)
    return salida, cambiadas[0]


def formato_del_rango(referencia, hojas, estilos):
    m = re.match(r"^'?([^'!]+)'?!\$?([A-Z]+)\$?(\d+)", referencia or '')
    if not m:
        return None
    hoja = hojas.get(m.group(1))
    if not hoja:
        return None
    c = re.search(r'<c r="%s%s"[^>]*\bs="(\d+)"' % (m.group(2), m.group(3)), hoja)
    if not c:
        return None
    i = int(c.group(1))
    return estilos[i]['formato'] if i < len(estilos) else None


def arreglar_etiquetas(chart_xml, hojas, estilos):
    m = re.search(r'<c:val>.*?<c:f>([^<]+)</c:f>', chart_xml, re.S)
    formato = formato_del_rango(m.group(1) if m else None, hojas, estilos)
    if not formato or formato == 'General':
        return chart_xml, False
    nuevo, n = re.subn(r'<c:numFmt formatCode="General" sourceLinked="1"/>',
                       '<c:numFmt formatCode="%s" sourceLinked="0"/>' % formato, chart_xml)
    return nuevo, n > 0


def main(entrada, salida):
    z = zipfile.ZipFile(entrada)
    piezas = {n: z.read(n) for n in z.namelist()}
    estilos_xml = piezas.get('xl/styles.xml', b'').decode('utf-8', 'replace')
    estilos = datos_de_estilos(estilos_xml)

    textos = []
    if 'xl/sharedStrings.xml' in piezas:
        crudo = piezas['xl/sharedStrings.xml'].decode('utf-8', 'replace')
        for t in re.findall(r'<si>(.*?)</si>', crudo, re.S):
            t = t.replace('<t/>', '')
            partes = re.findall(r'<t[^>]*>(.*?)</t>', t, re.S)
            texto = ''.join(partes)
            texto = (texto.replace('&#10;', '\n').replace('&amp;', '&')
                          .replace('&lt;', '<').replace('&gt;', '>'))
            textos.append(texto)

    libro = piezas.get('xl/workbook.xml', b'').decode('utf-8', 'replace')
    rels = piezas.get('xl/_rels/workbook.xml.rels', b'').decode('utf-8', 'replace')
    destino = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
    hojas = {}
    for m in re.finditer(r'<sheet[^>]*name="([^"]+)"[^>]*r:id="([^"]+)"', libro):
        clave = 'xl/' + destino.get(m.group(2), '').lstrip('/')
        if clave in piezas:
            hojas[m.group(1)] = piezas[clave].decode('utf-8', 'replace')

    nuevas, total_filas, total_graficos, total_col = {}, 0, 0, 0
    for nombre, crudo in piezas.items():
        if re.match(r'xl/worksheets/sheet\d+\.xml$', nombre):
            texto = crudo.decode('utf-8', 'replace')
            texto, anchos = ensanchar_columnas(texto)
            total_col += len(anchos)
            m = re.search(r'defaultColWidth="([\d.]+)"', texto)
            normal = a_pixeles(float(m.group(1))) if m else a_pixeles(8.43)
            texto, cuantas = poner_alturas(texto, estilos, textos, anchos, normal)
            total_filas += cuantas
            nuevas[nombre] = texto.encode('utf-8')
        elif re.match(r'xl/charts/chart\d+\.xml$', nombre):
            texto = crudo.decode('utf-8', 'replace')
            texto, tocado = arreglar_etiquetas(texto, hojas, estilos)
            if tocado:
                total_graficos += 1
            nuevas[nombre] = texto.encode('utf-8')

    # Una firma, para que el libro no se vuelva a arreglar cada vez que se suba:
    # si ya lleva `docProps`, deja de parecer recién salido de Google.
    hay_firma = 'docProps/app.xml' in piezas
    if not hay_firma:
        tipos = piezas.get('[Content_Types].xml', b'').decode('utf-8', 'replace')
        if tipos and 'docProps/app.xml' not in tipos:
            nuevas['[Content_Types].xml'] = tipos.replace('</Types>',
                '<Override PartName="/docProps/app.xml" ContentType="application/'
                'vnd.openxmlformats-officedocument.extended-properties+xml"/>'
                '</Types>').encode('utf-8')

    with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as fuera:
        for nombre in z.namelist():
            fuera.writestr(nombre, nuevas.get(nombre, piezas[nombre]))
        if not hay_firma:
            fuera.writestr('docProps/app.xml', FIRMA)
    print('columnas ensanchadas      : %d' % total_col)
    print('filas con su altura puesta: %d' % total_filas)
    print('gráficos con etiquetas ok : %d' % total_graficos)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2]))
