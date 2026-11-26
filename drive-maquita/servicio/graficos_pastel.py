# -*- coding: utf-8 -*-
"""Gráficos de pastel/anillo bajados de Google: el nombre junto a cada porción.

06/10/2026 («Análisis Mapa Inversiones», hoja «1 formación»): Google dibuja el
pastel con la «leyenda etiquetada», es decir, el nombre de cada provincia al
lado de su porción, unido con una línea, y sin cuadro de leyenda. Al exportar
escribe una leyenda normal a la derecha. Si las categorías vienen de celdas
combinadas («ESMERALDAS» ocupa A5:A7), esa leyenda sale con huecos en blanco y
el pastel, enorme. `graficos_google.sin_leyenda_de_una` ya quita la leyenda
(una sola serie), así que aquí se pone el nombre en la etiqueta de cada
porción, fuera y con su línea, como lo enseña Google.
"""
import re

_ORDEN = ('c:delete', 'c:numFmt', 'c:spPr', 'c:txPr', 'c:dLblPos', 'c:showLegendKey',
          'c:showVal', 'c:showCatName', 'c:showSerName', 'c:showPercent',
          'c:showBubbleSize', 'c:separator', 'c:showLeaderLines')


def _poner(bloque, etiqueta, valor):
    """Fija `<etiqueta val=…/>` dentro de un <c:dLbls> respetando el orden del esquema."""
    nuevo = '<%s val="%s"/>' % (etiqueta, valor)
    if re.search(r'<%s\b[^>]*/>' % etiqueta, bloque):
        return re.sub(r'<%s\b[^>]*/>' % etiqueta, nuevo, bloque, count=1)
    siguientes = _ORDEN[_ORDEN.index(etiqueta) + 1:]
    for otra in siguientes:
        m = re.search(r'<%s\b' % otra, bloque)
        if m:
            return bloque[:m.start()] + nuevo + bloque[m.start():]
    return bloque.replace('</c:dLbls>', nuevo + '</c:dLbls>')


def nombres_en_porciones(xml):
    """Pastel o anillo de una serie sin leyenda → etiqueta «nombre + valor» fuera, con línea."""
    tipo = re.search(r'<c:(pieChart|pie3DChart|doughnutChart)>', xml)
    if not tipo or len(re.findall(r'<c:ser>', xml)) != 1 or '<c:legend>' in xml:
        return xml, 0
    serie = re.search(r'<c:ser>.*?</c:ser>', xml, re.S)
    if not serie or '<c:cat>' not in serie.group(0):
        return xml, 0
    texto = serie.group(0)
    etiquetas = re.search(r'<c:dLbls>.*?</c:dLbls>', texto, re.S)
    if etiquetas:
        bloque = etiquetas.group(0)
        if re.search(r'<c:showCatName val="1"/>', bloque):
            return xml, 0
    else:
        bloque = '<c:dLbls><c:showLegendKey val="0"/><c:showVal val="1"/></c:dLbls>'
    bloque = _poner(bloque, 'c:showCatName', '1')
    bloque = _poner(bloque, 'c:showLeaderLines', '1')
    if tipo.group(1) != 'doughnutChart':          # el anillo no admite posición
        bloque = _poner(bloque, 'c:dLblPos', 'bestFit')
        # Fuera de la porción el texto blanco (el de «números dentro de la
        # barra») no se vería: gris oscuro, como Google.
        bloque = re.sub(r'(<c:txPr>.*?<a:srgbClr val=")FFFFFF(")', r'\g<1>404040\2', bloque, flags=re.S)
    if etiquetas:
        texto = texto[:etiquetas.start()] + bloque + texto[etiquetas.end():]
    else:                                          # va justo antes de <c:cat>
        texto = texto.replace('<c:cat>', bloque + '<c:cat>', 1)
    return xml[:serie.start()] + texto + xml[serie.end():], 1
