"""Vuelve a poner como GRÁFICOS los que Google exportó como imágenes.

Al bajar un libro de Google a `.xlsx`, los gráficos que Google no sabe convertir
—casi siempre porque sus datos salían de fórmulas que Excel no tiene, como
QUERY— se exportan como una imagen PNG llamada `ChartN.png`. Aquí se buscan esas
imágenes y se sustituyen por un gráfico de verdad, hecho con los datos de la
propia hoja.

De dónde salen los datos: se mira la tabla que hay a la IZQUIERDA de la imagen,
en la misma banda de filas. Es como están hechos estos informes (la tabla y su
gráfico, uno al lado del otro), y es lo que se ve en el libro del equipo.

Uso:  python3 rehacer_graficos_imagen.py entrada.xlsx salida.xlsx [--listar]

Con `--listar` solo dice qué encontraría, sin tocar el archivo.
"""
import re
import sys
import zipfile


def piezas_de(ruta):
    z = zipfile.ZipFile(ruta)
    return z, {n: z.read(n) for n in z.namelist()}


def texto(piezas, nombre):
    return piezas.get(nombre, b'').decode('utf-8', 'replace')


def hojas_del_libro(piezas):
    """[(nombre, ruta del xml)] en el orden del libro."""
    libro = texto(piezas, 'xl/workbook.xml')
    rels = texto(piezas, 'xl/_rels/workbook.xml.rels')
    destino = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
    salida = []
    for m in re.finditer(r'<sheet[^>]*name="([^"]+)"[^>]*r:id="([^"]+)"', libro):
        ruta = 'xl/' + destino.get(m.group(2), '').lstrip('/')
        if ruta in piezas:
            salida.append((m.group(1), ruta))
    return salida


def dibujo_de_la_hoja(piezas, ruta_hoja):
    s = texto(piezas, ruta_hoja)
    m = re.search(r'<drawing r:id="([^"]+)"', s)
    if not m:
        return None
    rel = ruta_hoja.replace('worksheets/', 'worksheets/_rels/') + '.rels'
    destino = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', texto(piezas, rel)))
    ruta = destino.get(m.group(1), '')
    return ('xl/' + ruta.replace('../', '')) if ruta else None


def imagenes_de_grafico(piezas, ruta_dibujo):
    """Las imágenes que en realidad eran gráficos: [(fila, columna, id, nombre)]."""
    d = texto(piezas, ruta_dibujo)
    rel = ruta_dibujo.replace('drawings/', 'drawings/_rels/') + '.rels'
    destino = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', texto(piezas, rel)))
    salida = []
    for tipo, cuerpo in re.findall(r'<xdr:(twoCellAnchor|oneCellAnchor|absoluteAnchor)[^>]*>(.*?)</xdr:\1>',
                                   d, re.S):
        if '<xdr:pic>' not in cuerpo:
            continue
        idr = re.search(r'r:embed="([^"]+)"', cuerpo)
        if not idr:
            continue
        fichero = destino.get(idr.group(1), '')
        nombre = re.search(r'name="([^"]*)"', cuerpo)
        # Solo las que Google llamó ChartN: las demás son imágenes de verdad
        if not re.search(r'Chart\d*\.png$', fichero, re.I):
            continue
        f = re.search(r'<xdr:col>(\d+)</xdr:col>.*?<xdr:row>(\d+)</xdr:row>', cuerpo, re.S)
        salida.append({
            'columna': int(f.group(1)) if f else 0,
            'fila': int(f.group(2)) if f else 0,
            'rel': idr.group(1),
            'fichero': fichero,
            'nombre': nombre.group(1) if nombre else ''
        })
    return salida


def celdas_de(hoja_xml):
    """{ (fila, columna): xml de la celda } en base 0.

    OJO: hay dos formas de escribir una celda, `<c .../>` (vacía) y
    `<c ...>…</c>`. Si solo se busca la segunda, las vacías se comen a las
    siguientes y se pierden columnas enteras."""
    salida = {}
    # Con `[^>]*` glotón, una celda vacía se comía a la siguiente: el patrón
    # llegaba hasta el `</c>` de la de al lado. Con la forma perezosa y la
    # autocerrada primero, cada celda queda en su sitio.
    for m in re.finditer(r'<c\b[^>]*?/>|<c\b[^>]*?>.*?</c>', hoja_xml, re.S):
        ref = re.match(r'<c\b[^>]*?r="([A-Z]+)(\d+)"', m.group(0))
        if not ref:
            continue
        columna = 0
        for ch in ref.group(1):
            columna = columna * 26 + (ord(ch) - 64)
        salida[(int(ref.group(2)) - 1, columna - 1)] = m.group(0)
    return salida


def tabla_a_la_izquierda(hoja_xml, fila, columna, alto=24):
    """Busca el bloque «etiqueta | número» más cercano por la izquierda, en la
       misma banda de filas que la imagen. Devuelve (col etiquetas, col valores,
       primera fila, última fila) en base 0, o None."""
    celdas = celdas_de(hoja_xml)
    mejor = None
    for c in range(max(0, columna - 1), 0, -1):
        filas = []
        for f in range(fila, fila + alto):
            etiqueta = celdas.get((f, c))
            valor = celdas.get((f, c + 1))
            if etiqueta and valor and 't="s"' in etiqueta and 't="s"' not in valor:
                filas.append(f)
        if len(filas) < 3:
            continue
        # Se parte en tramos seguidos y se toma el MÁS LARGO: en estos informes
        # hay varios bloques (ámbito, provincia, responsable) y el que interesa
        # es el que tiene más filas.
        tramos, actual = [], [filas[0]]
        for x in filas[1:]:
            if x == actual[-1] + 1:
                actual.append(x)
            else:
                tramos.append(actual)
                actual = [x]
        tramos.append(actual)
        tramos = [t for t in tramos if len(t) >= 3]
        if tramos:
            largo = max(tramos, key=len)
            candidato = (c, c + 1, largo[0], largo[-1])
            if not mejor or (candidato[3] - candidato[2]) > (mejor[3] - mejor[2]):
                mejor = candidato
            break
    return mejor


def letra(columna):
    salida = ''
    n = columna + 1
    while n:
        n, resto = divmod(n - 1, 26)
        salida = chr(65 + resto) + salida
    return salida


def chart_xml(hoja, cat, val, titulo):
    """Un gráfico de columnas, sencillo y con el mismo aire que los demás."""
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<c:chart>'
        + ('<c:title><c:tx><c:rich><a:bodyPr/><a:lstStyle/><a:p><a:r><a:t>%s</a:t></a:r></a:p>'
           '</c:rich></c:tx><c:overlay val="0"/></c:title>' % titulo if titulo else '')
        + '<c:autoTitleDeleted val="0"/><c:plotArea><c:layout/>'
        '<c:barChart><c:barDir val="col"/><c:grouping val="clustered"/><c:varyColors val="0"/>'
        '<c:ser><c:idx val="0"/><c:order val="0"/>'
        '<c:cat><c:strRef><c:f>%s</c:f></c:strRef></c:cat>'
        '<c:val><c:numRef><c:f>%s</c:f></c:numRef></c:val>'
        '</c:ser><c:gapWidth val="150"/><c:axId val="111111111"/><c:axId val="222222222"/>'
        '</c:barChart>'
        '<c:catAx><c:axId val="111111111"/><c:scaling><c:orientation val="minMax"/></c:scaling>'
        '<c:delete val="0"/><c:axPos val="b"/><c:crossAx val="222222222"/></c:catAx>'
        '<c:valAx><c:axId val="222222222"/><c:scaling><c:orientation val="minMax"/></c:scaling>'
        '<c:delete val="0"/><c:axPos val="l"/><c:numFmt formatCode="0%%" sourceLinked="0"/>'
        '<c:crossAx val="111111111"/></c:valAx>'
        '</c:plotArea><c:legend><c:legendPos val="r"/><c:overlay val="0"/></c:legend>'
        '<c:plotVisOnly val="1"/></c:chart></c:chartSpace>' % (cat, val))


def main(entrada, salida, solo_listar=False):
    z, piezas = piezas_de(entrada)
    cambios = []

    for nombre_hoja, ruta_hoja in hojas_del_libro(piezas):
        ruta_dibujo = dibujo_de_la_hoja(piezas, ruta_hoja)
        if not ruta_dibujo or ruta_dibujo not in piezas:
            continue
        hoja_xml = texto(piezas, ruta_hoja)
        for img in imagenes_de_grafico(piezas, ruta_dibujo):
            bloque = tabla_a_la_izquierda(hoja_xml, img['fila'], img['columna'])
            cambios.append({
                'hoja': nombre_hoja, 'ruta_hoja': ruta_hoja, 'dibujo': ruta_dibujo,
                'imagen': img, 'bloque': bloque
            })

    if not cambios:
        print('no hay gráficos convertidos en imagen: nada que hacer')
        return 0

    print('gráficos que Google convirtió en imagen:')
    for c in cambios:
        b = c['bloque']
        donde = ('datos %s%d:%s%d' % (letra(b[0]), b[2] + 1, letra(b[1]), b[3] + 1)) if b else 'sin datos claros'
        print('  · %s — %s en la fila %d, columna %s → %s'
              % (c['hoja'], c['imagen']['nombre'] or c['imagen']['fichero'],
                 c['imagen']['fila'] + 1, letra(c['imagen']['columna']), donde))
    if solo_listar:
        return 0

    # ── sustituir cada imagen por un gráfico ────────────────────────────
    nuevas = dict(piezas)
    cuantos = len(re.findall(r'xl/charts/chart\d+\.xml', ' '.join(piezas.keys())))
    tipos = texto(piezas, '[Content_Types].xml')
    hechos = 0

    for c in cambios:
        if not c['bloque']:
            continue
        b = c['bloque']
        hoja = c['hoja']
        entre = "'%s'!" % hoja if re.search(r'[\s\-]', hoja) else hoja + '!'
        cat = '%s$%s$%d:$%s$%d' % (entre, letra(b[0]), b[2] + 1, letra(b[0]), b[3] + 1)
        val = '%s$%s$%d:$%s$%d' % (entre, letra(b[1]), b[2] + 1, letra(b[1]), b[3] + 1)

        cuantos += 1
        ruta_chart = 'xl/charts/chart%d.xml' % cuantos
        nuevas[ruta_chart] = chart_xml(hoja, cat, val, c['imagen']['nombre']).encode('utf-8')

        # el dibujo: la imagen pasa a ser un marco de gráfico
        dibujo = nuevas[c['dibujo']].decode('utf-8', 'replace')
        rel_id = c['imagen']['rel']
        patron = re.compile(r'(<xdr:(?:one|two)CellAnchor[^>]*>.*?r:embed="%s".*?</xdr:(?:one|two)CellAnchor>)'
                            % re.escape(rel_id), re.S)
        m = patron.search(dibujo)
        if not m:
            continue
        trozo = m.group(1)
        marco = re.sub(r'<xdr:pic>.*?</xdr:pic>',
                       '<xdr:graphicFrame><xdr:nvGraphicFramePr>'
                       '<xdr:cNvPr id="%d" name="%s"/><xdr:cNvGraphicFramePr/>'
                       '</xdr:nvGraphicFramePr><xdr:xfrm><a:off x="0" y="0"/>'
                       '<a:ext cx="0" cy="0"/></xdr:xfrm>'
                       '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/'
                       'drawingml/2006/chart"><c:chart xmlns:c="http://schemas.openxmlformats.org/'
                       'drawingml/2006/chart" xmlns:r="http://schemas.openxmlformats.org/'
                       'officeDocument/2006/relationships" r:id="%s"/></a:graphicData></a:graphic>'
                       '</xdr:graphicFrame>' % (9000 + cuantos, c['imagen']['nombre'] or 'Gráfico', rel_id),
                       trozo, flags=re.S)
        dibujo = dibujo.replace(trozo, marco)
        nuevas[c['dibujo']] = dibujo.encode('utf-8')

        # el enlace del dibujo: ahora apunta al gráfico, no a la imagen
        rel_dibujo = c['dibujo'].replace('drawings/', 'drawings/_rels/') + '.rels'
        rels = nuevas[rel_dibujo].decode('utf-8', 'replace')
        rels = re.sub(r'(<Relationship[^>]*Id="%s"[^>]*Type=")[^"]*("[^>]*Target=")[^"]*(")'
                      % re.escape(rel_id),
                      r'\1http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart'
                      r'\2../charts/chart%d.xml\3' % cuantos, rels)
        nuevas[rel_dibujo] = rels.encode('utf-8')

        if 'chart%d.xml' % cuantos not in tipos:
            tipos = tipos.replace('</Types>',
                '<Override PartName="/xl/charts/chart%d.xml" ContentType="application/'
                'vnd.openxmlformats-officedocument.drawingml.chart+xml"/></Types>' % cuantos)
        hechos += 1

    nuevas['[Content_Types].xml'] = tipos.encode('utf-8')

    with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as fuera:
        for nombre in list(z.namelist()) + [n for n in nuevas if n not in z.namelist()]:
            fuera.writestr(nombre, nuevas.get(nombre, piezas.get(nombre, b'')))
    print('gráficos rehechos: %d' % hechos)
    return 0


if __name__ == '__main__':
    argumentos = [a for a in sys.argv[1:] if not a.startswith('--')]
    sys.exit(main(argumentos[0], argumentos[1] if len(argumentos) > 1 else 'salida.xlsx',
                  '--listar' in sys.argv))
