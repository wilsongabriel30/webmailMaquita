# -*- coding: utf-8 -*-
"""Prueba de graficos_google: un .xlsx como los que exporta Google Sheets se
arregla (etiquetas con el formato de la celda, eje 0–100 %, sin leyenda de una
sola serie) sin tocar nada más, y uno que ya está bien no se toca.

El archivo de muestra se fabrica aquí mismo: así no hay que arrastrar un binario.

Uso: cd /home/sistemas/almacen-maquita/pruebas && python3 prueba-graficos-google.py
"""
import os
import sys
import xml.etree.ElementTree as ET
import zipfile

sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/../servicio')
import graficos_google as G                                       # noqa: E402

rojo = 0


def bien(ok, que):
    global rojo
    if not ok:
        rojo += 1
    print(('OK   ' if ok else 'MAL  ') + que)


CHART = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<c:chartSpace xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart"
 xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><c:chart><c:plotArea><c:layout/>
<c:barChart><c:barDir val="col"/><c:ser><c:idx val="0"/><c:order val="0"/>
<c:dLbls><c:numFmt formatCode="General" sourceLinked="1"/><c:showVal val="1"/></c:dLbls>
<c:cat><c:strRef><c:f>'Datos'!$B$2:$B$4</c:f></c:strRef></c:cat>
<c:val><c:numRef><c:f>'Datos'!$C$2:$C$4</c:f></c:numRef></c:val>
</c:ser><c:axId val="111"/><c:axId val="222"/></c:barChart>
<c:catAx><c:axId val="111"/><c:scaling><c:orientation val="minMax"/></c:scaling>
<c:delete val="0"/><c:axPos val="b"/><c:crossAx val="222"/></c:catAx>
<c:valAx><c:axId val="222"/><c:scaling><c:orientation val="minMax"/></c:scaling>
<c:delete val="0"/><c:axPos val="l"/><c:numFmt formatCode="General" sourceLinked="1"/>
<c:crossAx val="111"/></c:valAx></c:plotArea>
<c:legend><c:legendPos val="r"/><c:overlay val="0"/></c:legend>
<c:plotVisOnly val="1"/></c:chart></c:chartSpace>"""

HOJA = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
<row r="2"><c r="B2" t="s"><v>0</v></c><c r="C2" s="1"><v>0.58</v></c></row>
<row r="3"><c r="B3" t="s"><v>1</v></c><c r="C3" s="1"><v>0.633333333</v></c></row>
<row r="4"><c r="B4" t="s"><v>2</v></c><c r="C4" s="1"><v>0.25</v></c></row>
</sheetData></worksheet>"""

ESTILOS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
<xf numFmtId="9" fontId="0" fillId="0" borderId="0" applyNumberFormat="1"/></cellXfs>
</styleSheet>"""

LIBRO = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet state="visible" name="Datos" sheetId="1" r:id="rId1"/></sheets></workbook>"""

RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
 Target="worksheets/sheet1.xml"/></Relationships>"""


def libro(chart=CHART, estilos=ESTILOS):
    ruta = '/tmp/prueba-graficos-%d.xlsx' % os.getpid()
    with zipfile.ZipFile(ruta, 'w') as z:
        z.writestr('xl/workbook.xml', LIBRO)
        z.writestr('xl/_rels/workbook.xml.rels', RELS)
        z.writestr('xl/worksheets/sheet1.xml', HOJA)
        z.writestr('xl/styles.xml', estilos)
        z.writestr('xl/charts/chart1.xml', chart)
        z.writestr('xl/media/Chart1.png', b'\x89PNG imagen de un grafico de Google')
    return ruta


# ── el formato se saca de las celdas de la serie ─────────────────────────
origen = libro()
with zipfile.ZipFile(origen) as z:
    hojas = G._hojas_por_nombre(z)
    formatos = G._formatos_de_estilo(z)
    bien(hojas == {'Datos': 'xl/worksheets/sheet1.xml'}, 'encuentra la hoja por su nombre')
    bien(formatos[1] == '0%', 'lee el formato de las celdas (numFmtId 9 → 0%)')
    bien(G.formato_de_la_serie(z, hojas, formatos, "'Datos'!$C$2:$C$4") == '0%',
         'y lo asocia a la serie del gráfico')
    bien(G.formato_de_la_serie(z, hojas, formatos, "'No existe'!$A$1:$A$2") == '',
         'si la hoja no existe, no inventa formato')
    bien(G.formato_de_la_serie(z, hojas, formatos, "&apos;Datos&apos;!$C$2:$C$4") == '0%',
         'y entiende la referencia escapada que deja el editor al guardar (&apos;)')

bien(G.es_porcentaje('0%') and G.es_porcentaje('0.00%') and not G.es_porcentaje('#,##0.00'),
     'sabe distinguir un formato de porcentaje')

# ── qué se arreglaría ────────────────────────────────────────────────────
informe = G.revisar(origen)
bien(informe['xl/charts/chart1.xml'] == {'etiquetas': '0%', 'eje': '0–100 %', 'eje en %': '0%',
                                         'numeros': 'dentro de la barra',
                                         'barras': 'anchas como en Google', 'leyenda': 'quitada'},
     've los defectos del gráfico de Google: %s' % informe['xl/charts/chart1.xml'])

destino = '/tmp/prueba-graficos-salida.xlsx'
informe = G.arreglar(origen, destino)
bien(bool(informe), 'y los arregla')

with zipfile.ZipFile(origen) as a, zipfile.ZipFile(destino) as b:
    bien(set(a.namelist()) == set(b.namelist()), 'no se pierde ni se añade ninguna pieza del archivo')
    cambiadas = [n for n in a.namelist() if a.read(n) != b.read(n)]
    bien(cambiadas == ['xl/charts/chart1.xml'], 'solo se toca el XML del gráfico: %s' % cambiadas)
    x = b.read('xl/charts/chart1.xml').decode()

try:
    ET.fromstring(x)
    bien(True, 'el gráfico sigue siendo XML válido')
except ET.ParseError as e:
    bien(False, 'el gráfico sigue siendo XML válido (%s)' % e)

bien('<c:numFmt formatCode="0%" sourceLinked="0"/>' in x,
     'las etiquetas ya piden el formato de la celda («63%», no «0,633333333»)')
bien('<c:max val="1"/><c:min val="0"/>' in x, 'el eje va de 0 a 100 % (y no hasta el 120 %)')
bien('<c:majorUnit val="0.25"/>' in x, 'con divisiones de 25 %, como las de Google')
bien('<c:legend>' not in x, 'la leyenda de una sola serie se quita')
bien('<c:dLblPos val="inEnd"/>' in x, 'los números van DENTRO de la barra, arriba (como Google)')
bien('<a:srgbClr val="FFFFFF"/>' in x.split('<c:dLbls>')[1].split('</c:dLbls>')[0],
     'y en blanco, porque la barra es oscura')
bien('algn="ctr"' in x, 'centrados en la barra (si no, OnlyOffice los pega a la izquierda)')
bien('<c:gapWidth val="50"/>' in x, 'las barras se ensanchan para que el número quepa dentro')
eje = x[x.index('<c:valAx>'):x.index('</c:valAx>')]
bien('<c:numFmt formatCode="0%" sourceLinked="0"/>' in eje,
     'el eje también sale en porcentaje (0 %, 25 %…) y no en decimales')

# ── los «None» de los títulos de eje vacíos ──────────────────────────────
conTitulos = CHART.replace('<c:axPos val="b"/>',
    '<c:axPos val="b"/><c:title><c:tx><c:rich><a:p><a:r><a:t>\n</a:t></a:r></a:p></c:rich></c:tx></c:title>')
conTitulos = conTitulos.replace('<c:axPos val="l"/>',
    '<c:axPos val="l"/><c:title><c:tx><c:rich><a:p><a:r><a:t>Mi eje</a:t></a:r></a:p></c:rich></c:tx></c:title>')
libroTitulos = libro(chart=conTitulos)
informeT = G.revisar(libroTitulos)['xl/charts/chart1.xml']
bien(informeT.get('titulos') == 'sin los «None» de los ejes', 'quita el título de eje vacío (el «None»)')
G.arreglar(libroTitulos, '/tmp/prueba-graficos-titulos.xlsx')
with zipfile.ZipFile('/tmp/prueba-graficos-titulos.xlsx') as z:
    t = z.read('xl/charts/chart1.xml').decode()
bien('Mi eje' in t, 'pero respeta el título de eje que sí dice algo')

# el editor, al guardar, deja escrito «None» y `sourceLinked="0"`
comoElEditor = conTitulos.replace('<a:t>\n</a:t>', '<a:t>None</a:t>').replace(
    '<c:numFmt formatCode="General" sourceLinked="1"/>', '<c:numFmt formatCode="General" sourceLinked="0"/>')
libroEditor = libro(chart=comoElEditor)
informeE = G.revisar(libroEditor)['xl/charts/chart1.xml']
bien(informeE.get('titulos') == 'sin los «None» de los ejes',
     'reconoce el «None» que deja escrito el editor')
bien(informeE.get('eje en %') == '0%' and informeE.get('etiquetas') == '0%',
     'y el formato «General» aunque venga con sourceLinked="0": %s' % informeE)
bien(x.index('</c:ser>') < x.index('<c:gapWidth'), 'gapWidth va tras las series, como manda el esquema')
bien(G._texto_sobre('1383B1') == 'FFFFFF' and G._texto_sobre('FCE8B2') == '000000',
     'sobre un color claro el número saldría en negro')
bien(x.index('<c:crossAx val="111"/>') < x.index('<c:majorUnit'),
     'majorUnit va después de crossAx, que es lo que manda el formato')

# ── un archivo que ya está bien no se toca ───────────────────────────────
yaBueno = libro(chart=x)
bien(G.arreglar(yaBueno, '/tmp/prueba-graficos-nada.xlsx') == {},
     'pasarlo dos veces no cambia nada (no se acumulan arreglos)')

# ── sin formato de porcentaje, el eje se deja en paz ─────────────────────
sinPorcentaje = ESTILOS.replace('numFmtId="9"', 'numFmtId="0"')
otro = libro(estilos=sinPorcentaje)
informe = G.revisar(otro)['xl/charts/chart1.xml']
bien('eje' not in informe and 'etiquetas' not in informe,
     'si los datos no son porcentajes, ni etiquetas ni eje se tocan: %s' % informe)
bien(informe.get('leyenda') == 'quitada', 'pero la leyenda de una sola serie sí sobra igual')

# ── un archivo que YA pasó por el editor (valores por defecto de OnlyOffice) ──
delEditor = libro(chart=x.replace('<c:gapWidth val="50"/>', '<c:gapWidth val="150"/>')
                       .replace('<c:dLblPos val="inEnd"/>', '<c:dLblPos val="outEnd"/>'))
bien(G.revisar(delEditor)['xl/charts/chart1.xml'] == {},
     'sin forzar no se pisa lo que el editor (o la gente) haya dejado puesto')
informe = G.revisar(delEditor, forzar=True)['xl/charts/chart1.xml']
bien(informe == {'numeros': 'dentro de la barra', 'barras': 'anchas como en Google'},
     'con --forzar se vuelve a poner el aspecto de Google: %s' % informe)
G.arreglar(delEditor, '/tmp/prueba-graficos-forzado.xlsx', forzar=True)
with zipfile.ZipFile('/tmp/prueba-graficos-forzado.xlsx') as z:
    y = z.read('xl/charts/chart1.xml').decode()
bien('<c:dLblPos val="inEnd"/>' in y and '<c:dLblPos val="outEnd"/>' not in y,
     'y el número vuelve a ir dentro de la barra')
bien('<c:gapWidth val="50"/>' in y and '<c:gapWidth val="150"/>' not in y, 'y la barra vuelve a ser ancha')
bien(G.revisar('/tmp/prueba-graficos-forzado.xlsx', forzar=True)['xl/charts/chart1.xml'] == {},
     'forzar dos veces tampoco cambia nada')

# ── arreglar en su sitio (lo que hace la subida) ─────────────────────────
enSitio = libro()
antes = os.path.getsize(enSitio)
informe = G.arreglar_en_sitio(enSitio)
bien(bool(informe) and os.path.getsize(enSitio) != antes, 'arregla el archivo donde está (subida)')
bien(G.arreglar_en_sitio(enSitio) == {}, 'y pasarlo otra vez ya no cambia nada')
bien(not os.path.exists(enSitio + '.graficos'), 'no deja temporales tirados')
noEsHoja = '/tmp/prueba-graficos-no.txt'
open(noEsHoja, 'w').write('esto no es una hoja')
bien(G.arreglar_en_sitio(noEsHoja) == {}, 'un archivo que no es .xlsx ni se abre')
bien(G.arreglar_en_sitio(libro(), tope=10) == {}, 'un archivo enorme se deja en paz (tope de tamaño)')

for f in (origen, destino, yaBueno, otro, enSitio, noEsHoja, delEditor, libroTitulos, libroEditor,
          '/tmp/prueba-graficos-titulos.xlsx',
          '/tmp/prueba-graficos-nada.xlsx', '/tmp/prueba-graficos-forzado.xlsx'):
    try:
        os.unlink(f)
    except OSError:
        pass

print()
print('✓ %d comprobaciones, %d en rojo' % (40, rojo))
sys.exit(1 if rojo else 0)
