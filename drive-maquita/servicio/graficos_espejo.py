# -*- coding: utf-8 -*-
"""Que cada gráfico se dibuje en el editor del Drive como en Google (20/10/2026).

Comparando los gráficos de «Análisis Mapa Inversiones» dibujados por el motor
de Google (exportación HTML) con el editor del Drive:

  1. **Colores cambiados en los pasteles.** Si la serie abarca filas vacías
     (celdas combinadas: ESMERALDAS ocupa A5:A20), Google da un color a cada
     porción QUE SE VE, pero en el .xlsx lo escribe en los puntos 0, 1, 2… del
     rango. El editor pinta por punto: solo la primera porción salía con su
     color. Se ponen los colores de Google en los puntos que tienen valor.
  2. **Leyenda etiquetada.** El pastel de Google lleva, junto a cada porción,
     el nombre y el porcentaje con una línea, y no tiene cuadro de leyenda (si
     no se eligió otra cosa). Si pide el valor DENTRO de la porción
     (`pieSliceText: value`), el valor va también en la etiqueta: el editor no
     admite dos etiquetas por porción.
  3. **Título** a la izquierda, en gris (757575), sin negrita y en una línea.
  4. **Números de las barras** encima, del color de la barra y con el formato
     de la columna («$10.041,59»), cuando Google los pinta así; leyenda arriba
     cuando hay varias series y ninguna si Google la quitó; textos del eje
     horizontal sin inclinar salvo que Google los incline.
  5. **Letra Arial**, como la de los gráficos de Google (no la del tema).

Con la definición de Google (graficos_definiciones.py) se usan sus opciones;
sin ella, lo que Google hace por defecto. Trabaja sobre el XML del gráfico.
"""
import html
import re

PALETA = ('4285F4', 'EA4335', 'FBBC04', '34A853', 'FF6D01', '46BDC6', '7BAAF7', 'F07B72',
          'FCD04F', '71C287', 'FF994D', '7ED1D7', 'B3CEFB', 'F7CBC7', 'FDE49B', 'AEDCBA')
TITULO = {'sz': 1350, 'color': '757575'}
ETIQUETA = {'sz': 900, 'color': '1A1A1A'}
LETRA = 'Arial'
_PASTEL = re.compile(r'<c:(pieChart|pie3DChart|doughnutChart)>')
_LEYENDA = {'right': 'r', 'left': 'l', 'top': 't', 'bottom': 'b'}
_POSICION = {'insideEnd': 'inEnd', 'center': 'ctr', 'insideBase': 'inBase', 'outsideEnd': 'outEnd'}


# ── piezas de texto ───────────────────────────────────────────────────────
def _relleno(color):
    return '<a:solidFill><a:srgbClr val="%s"/></a:solidFill>' % color


def _txpr(sz, color, negrita=False, giro=None):
    cuerpo = '<a:bodyPr rot="%d" vert="horz"/>' % giro if giro is not None else '<a:bodyPr/>'
    return ('<c:txPr>%s<a:lstStyle/><a:p><a:pPr><a:defRPr sz="%d" b="%d">%s<a:latin typeface="%s"/>'
            '</a:defRPr></a:pPr><a:endParaRPr lang="es-EC"/></a:p></c:txPr>'
            % (cuerpo, sz, 1 if negrita else 0, _relleno(color), LETRA))


def _formato(codigo):
    return '<c:numFmt formatCode="%s" sourceLinked="0"/>' % html.escape(codigo, quote=True)


def fuente_google(xml):
    """La letra del tema (+mn-lt, Calibri) por Arial, en todo el gráfico."""
    nuevo = xml.replace('typeface="+mn-lt"', 'typeface="%s"' % LETRA)
    if '<c:txPr>' not in xml.split('</c:chart>', 1)[-1]:
        general = _txpr(1000, '222222')
        nuevo = nuevo.replace('</c:chart>', '</c:chart>' + general, 1) if '<c:spPr' not in nuevo.split('</c:chart>', 1)[-1] \
            else re.sub(r'(</c:chart>\s*<c:spPr\b.*?</c:spPr>)', lambda m: m.group(1) + general, nuevo, count=1, flags=re.S)
    return nuevo, int(nuevo != xml)


def titulo_google(xml):
    """El título del gráfico como Google: arriba a la izquierda, gris, sin negrita."""
    m = re.search(r'(<c:chart>\s*)(<c:title>.*?</c:title>)', xml, re.S)
    if not m:
        return xml, 0
    bloque = m.group(2)
    textos = re.findall(r'<a:t>([^<]*)</a:t>', bloque)
    if not textos:
        return xml, 0
    corrida = ''.join('<a:r><a:rPr lang="es-EC" sz="%d" b="0">%s<a:latin typeface="%s"/></a:rPr><a:t>%s</a:t></a:r>'
                      % (TITULO['sz'], _relleno(TITULO['color']), LETRA, t) for t in textos)
    nuevo = ('<c:title><c:tx><c:rich><a:bodyPr/><a:lstStyle/><a:p><a:pPr algn="l"><a:defRPr sz="%d" b="0">%s'
             '<a:latin typeface="%s"/></a:defRPr></a:pPr>%s</a:p></c:rich></c:tx>'
             '<c:layout><c:manualLayout><c:xMode val="edge"/><c:yMode val="edge"/>'
             '<c:x val="0.03"/><c:y val="0.03"/></c:manualLayout></c:layout>'
             '<c:overlay val="0"/></c:title>' % (TITULO['sz'], _relleno(TITULO['color']), LETRA, corrida))
    if nuevo == bloque:
        return xml, 0
    return xml[:m.start(2)] + nuevo + xml[m.end(2):], 1


def color_de_serie(serie, k=0):
    """El relleno propio de la serie; los colores del tema de Google (accent1…6)
    son los primeros de su paleta."""
    propio = re.search(r'</c:tx>\s*<c:spPr>(.*?)</c:spPr>|<c:order val="\d+"/>\s*<c:spPr>(.*?)</c:spPr>', serie, re.S)
    bloque = (propio.group(1) or propio.group(2)) if propio else ''
    fijo = re.search(r'<a:solidFill>\s*<a:srgbClr val="([0-9A-Fa-f]{6})"', bloque)
    if fijo:
        return fijo.group(1).upper()
    tema = re.search(r'<a:solidFill>\s*<a:schemeClr val="accent([1-6])"', bloque)
    return PALETA[int(tema.group(1)) - 1] if tema else PALETA[k % len(PALETA)]


def _sin_leyenda(xml):
    return re.sub(r'<c:legend>.*?</c:legend>', '', xml, flags=re.S)


def _leyenda_en(xml, lugar):
    if '<c:legend>' in xml:
        return re.sub(r'<c:legendPos val="\w+"/>', '<c:legendPos val="%s"/>' % lugar, xml, count=1)
    leyenda = '<c:legend><c:legendPos val="%s"/><c:overlay val="0"/>%s</c:legend>' % (lugar, _txpr(900, '222222'))
    return xml.replace('</c:plotArea>', '</c:plotArea>' + leyenda, 1)


# ── pasteles ──────────────────────────────────────────────────────────────
def colores_por_porcion(xml, con_valor):
    """Los colores de Google, en los puntos que tienen valor (en el orden de Google)."""
    serie = re.search(r'<c:ser>.*?</c:ser>', xml, re.S)
    if not serie or not con_valor:
        return xml, 0
    texto = serie.group(0)
    puntos = re.findall(r'<c:dPt>.*?</c:dPt>', texto, re.S)
    colores = [c for c in (re.search(r'<a:srgbClr val="([0-9A-Fa-f]{6})"', p) for p in puntos) if c]
    colores = [c.group(1).upper() for c in colores] or list(PALETA)
    nuevos = ''.join('<c:dPt><c:idx val="%d"/><c:bubble3D val="0"/><c:spPr>%s<a:ln><a:noFill/></a:ln></c:spPr></c:dPt>'
                     % (indice, _relleno(colores[k] if k < len(colores) else PALETA[k % len(PALETA)]))
                     for k, indice in enumerate(con_valor))
    sin_puntos = re.sub(r'<c:dPt>.*?</c:dPt>', '', texto, flags=re.S)
    # dPt va tras idx/order/tx/spPr/explosion y antes de dLbls/cat/val.
    ancla = re.search(r'<c:dLbls>|<c:cat>|<c:val>', sin_puntos)
    if not ancla:
        return xml, 0
    nuevo = sin_puntos[:ancla.start()] + nuevos + sin_puntos[ancla.start():]
    if nuevo == texto:
        return xml, 0
    return xml[:serie.start()] + nuevo + xml[serie.end():], 1


def leyenda_del_pastel(xml, opciones, formato=''):
    """«Leyenda etiquetada» de Google: nombre y porcentaje junto a cada porción."""
    tipo = _PASTEL.search(xml)
    if not tipo or len(re.findall(r'<c:ser>', xml)) != 1:
        return xml, 0
    leyenda = opciones.get('legend')
    lugar = leyenda.get('position') if isinstance(leyenda, dict) else leyenda
    lugar = lugar or 'labeled'
    if lugar in _LEYENDA:
        return _leyenda_en(xml, _LEYENDA[lugar]), 1
    if lugar not in ('labeled', 'none'):
        return xml, 0
    con_valor = opciones.get('pieSliceText') == 'value'
    nombre = lugar == 'labeled'
    if not (nombre or con_valor):
        return _sin_leyenda(xml), 1
    partes = ['<c:dLbls>']
    if con_valor and formato:
        partes.append(_formato(formato))
    elif nombre:
        partes.append(_formato('0.0%'))           # Google: «37,2 %», con un decimal
    partes.append('<c:spPr><a:noFill/><a:ln><a:noFill/></a:ln></c:spPr>')
    partes.append(_txpr(ETIQUETA['sz'], ETIQUETA['color']))
    if tipo.group(1) != 'doughnutChart':          # el anillo no admite posición
        partes.append('<c:dLblPos val="%s"/>' % ('outEnd' if nombre else 'ctr'))
    partes.append('<c:showLegendKey val="0"/><c:showVal val="%d"/><c:showCatName val="%d"/>'
                  '<c:showSerName val="0"/><c:showPercent val="%d"/><c:showBubbleSize val="0"/>'
                  % (int(con_valor), int(nombre), int(nombre)))
    partes.append('<c:separator>\n</c:separator><c:showLeaderLines val="1"/></c:dLbls>')
    etiquetas = ''.join(partes)
    serie = re.search(r'<c:ser>.*?</c:ser>', xml, re.S)
    texto = re.sub(r'<c:dLbls>.*?</c:dLbls>', '', serie.group(0), count=1, flags=re.S)
    texto = re.sub(r'(<c:cat>|<c:val>)', etiquetas + r'\1', texto, count=1)
    nuevo = _sin_leyenda(xml[:serie.start()] + texto + xml[serie.end():])
    return nuevo, int(nuevo != xml)


# ── barras y columnas ─────────────────────────────────────────────────────
def leyenda_de_barras(xml, opciones):
    """Sin leyenda si Google la quitó o hay una sola serie; arriba si hay varias."""
    if not re.search(r'<c:(barChart|bar3DChart|lineChart|areaChart)>', xml):
        return xml, 0
    leyenda = opciones.get('legend')
    lugar = leyenda.get('position') if isinstance(leyenda, dict) else leyenda
    series = len(re.findall(r'<c:ser>', xml))
    if lugar == 'none' or (not lugar and series < 2):
        nuevo = _sin_leyenda(xml)
    elif lugar in _LEYENDA or not lugar:
        nuevo = _leyenda_en(xml, _LEYENDA.get(lugar, 't'))
    else:
        return xml, 0
    return nuevo, int(nuevo != xml)


def numeros_de_barras(xml, opciones, formatos):
    """Los números de cada serie donde y como los pinta Google."""
    if not re.search(r'<c:(barChart|bar3DChart|lineChart)>', xml):
        return xml, 0
    series_google = opciones.get('series') or {}
    cambios = [0]

    def serie(m):
        texto = m.group(0)
        orden = re.search(r'<c:order val="(\d+)"/>', texto)
        k = int(orden.group(1)) if orden else 0
        propia = series_google.get(str(k)) or {}
        if propia.get('dataLabel') != 'value':
            return texto
        color = color_de_serie(texto, k)
        lugar = _POSICION.get(propia.get('dataLabelPlacement'), 'outEnd')
        dentro = lugar in ('inEnd', 'ctr', 'inBase')
        partes = ['<c:dLbls>']
        if k + 1 < len(formatos) and formatos[k + 1]:
            partes.append(_formato(formatos[k + 1]))
        partes.append('<c:spPr><a:noFill/><a:ln><a:noFill/></a:ln></c:spPr>')
        partes.append(_txpr(900, 'FFFFFF' if dentro else color))
        partes.append('<c:dLblPos val="%s"/><c:showLegendKey val="0"/><c:showVal val="1"/><c:showCatName val="0"/>'
                      '<c:showSerName val="0"/><c:showPercent val="0"/><c:showBubbleSize val="0"/></c:dLbls>' % lugar)
        nuevo = re.sub(r'<c:dLbls>.*?</c:dLbls>', '', texto, count=1, flags=re.S)
        nuevo = re.sub(r'(<c:trendline>|<c:errBars>|<c:cat>|<c:val>)', ''.join(partes) + r'\1', nuevo, count=1)
        if nuevo != texto:
            cambios[0] += 1
        return nuevo
    return re.sub(r'<c:ser>.*?</c:ser>', serie, xml, flags=re.S), cambios[0]


def eje_horizontal(xml, opciones, formatos):
    """Textos del eje de categorías rectos (o inclinados si Google los inclina) y
    el eje de valores con el formato de la primera serie."""
    if not re.search(r'<c:(barChart|bar3DChart|lineChart|areaChart)>', xml):
        return xml, 0
    eje_h = opciones.get('hAxis') or {}
    giro = -2700000 if eje_h.get('slantedText') else 0
    nuevo = xml
    cat = re.search(r'<c:catAx>.*?</c:catAx>', nuevo, re.S)
    if cat:
        bloque = cat.group(0)
        cuerpo = re.sub(r'<c:txPr>.*?</c:txPr>', '', bloque, flags=re.S)
        cuerpo = re.sub(r'(<c:crossAx\b)', _txpr(900, '222222', giro=giro) + r'\1', cuerpo, count=1)
        nuevo = nuevo.replace(bloque, cuerpo, 1)
    val = re.search(r'<c:valAx>.*?</c:valAx>', nuevo, re.S)
    if val and len(formatos) > 1 and formatos[1] and '%' not in formatos[1]:
        bloque = val.group(0)
        cuerpo = re.sub(r'<c:numFmt [^>]*/>', _formato(formatos[1]), bloque, count=1)
        nuevo = nuevo.replace(bloque, cuerpo, 1)
    return nuevo, int(nuevo != xml)


def paso_redondo(maximo, tramos=5):
    """El paso de las líneas de guía que elige Google: el menor de 1 · 2 · 2,5 · 5
    (×10ⁿ) con el que el máximo cabe en `tramos` tramos."""
    if not maximo or maximo <= 0:
        return None
    potencia = 10 ** (len(str(int(maximo))) - 2) if maximo >= 10 else 0.1
    while True:
        for base in (1, 2, 2.5, 5):
            paso = base * potencia
            if maximo / paso <= tramos + 1e-9:
                return paso
        potencia *= 10


def escala_de_valores(xml, definicion):
    """Las líneas de guía del eje de valores cada «paso redondo», como Google.
    Solo el paso: el máximo lo sigue calculando el editor (si los datos crecen, el eje crece)."""
    if not re.search(r'<c:(barChart|bar3DChart|lineChart|areaChart)>', xml) or not definicion:
        return xml, 0
    if any('%' in (c.get('formato') or '') for c in definicion.get('columnas') or []):
        return xml, 0                              # porcentajes: eje 0–100 % (graficos_google)
    numeros = [v for fila in definicion.get('filas') or [] for v in fila[1:] if isinstance(v, (int, float))]
    if not numeros or min(numeros) < 0:
        return xml, 0
    paso = paso_redondo(max(numeros))
    val = re.search(r'<c:valAx>.*?</c:valAx>', xml, re.S)
    if not paso or not val:
        return xml, 0
    bloque = val.group(0)
    unidad = '<c:majorUnit val="%s"/>' % ('%g' % paso)
    cuerpo = re.sub(r'<c:majorUnit val="[^"]*"/>', '', bloque)
    ancla = re.search(r'<c:minorUnit|<c:dispUnits|<c:extLst|</c:valAx>', cuerpo)
    cuerpo = cuerpo[:ancla.start()] + unidad + cuerpo[ancla.start():]
    return (xml.replace(bloque, cuerpo, 1), 1) if cuerpo != bloque else (xml, 0)


# ── entrada ──────────────────────────────────────────────────────────────
def arreglar(xml, definicion=None, con_valor=None, formato=''):
    """El gráfico como en Google. `definicion`: la de graficos_definiciones (o
    None: lo que Google hace por defecto); `con_valor`: índices de los puntos
    con valor de la serie (pasteles); `formato`: formato de número de la serie."""
    definicion = definicion or {}
    opciones = definicion.get('opciones') or {}
    formatos = [c.get('formato', '') for c in definicion.get('columnas') or []]
    if not formatos and formato:
        formatos = ['', formato]
    hecho = {}
    for clave, (funcion, argumentos) in (
            ('letra', (fuente_google, ())),
            ('titulo', (titulo_google, ())),
            ('colores', (colores_por_porcion, (con_valor,))),
            ('pastel', (leyenda_del_pastel, (opciones, formatos[1] if len(formatos) > 1 else ''))),
            ('leyenda', (leyenda_de_barras, (opciones,))),
            ('numeros', (numeros_de_barras, (opciones, formatos))),
            ('ejes', (eje_horizontal, (opciones, formatos))),
            ('escala', (escala_de_valores, (definicion,)))):
        if clave == 'colores' and not (_PASTEL.search(xml) and con_valor):
            continue
        xml, n = funcion(xml, *argumentos)
        if n:
            hecho[clave] = n
    return xml, hecho
