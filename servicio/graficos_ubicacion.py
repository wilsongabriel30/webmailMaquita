# -*- coding: utf-8 -*-
"""Dónde está cada gráfico de un .xlsx y qué puntos de su serie tienen valor (20/10/2026).

Lo necesita graficos_espejo.py: para emparejar cada `xl/charts/chartN.xml`
con su definición de Google (misma hoja y ancla más cercana) y para saber a
qué puntos del rango corresponde cada color de un pastel. Solo biblioteca estándar.
"""
import html
import posixpath
import re

import graficos_definiciones


def _rels(z, pieza):
    """{rId: pieza destino} de las relaciones de una pieza del ZIP."""
    carpeta, nombre = posixpath.split(pieza)
    ruta = posixpath.join(carpeta, '_rels', nombre + '.rels')
    try:
        texto = z.read(ruta).decode('utf-8', 'replace')
    except KeyError:
        return {}
    return {m.group(1): posixpath.normpath(posixpath.join(carpeta, m.group(2)))
            for m in re.finditer(r'Id="(rId\d+)"[^>]*?Target="([^"]+)"', texto)}


def graficos_por_hoja(z, hojas):
    """{pieza del gráfico: (hoja, fila, columna)} — fila y columna desde 0, como el ancla."""
    salida = {}
    for hoja, pieza in hojas.items():
        for destino in _rels(z, pieza).values():
            if '/drawings/' not in destino:
                continue
            try:
                dibujo = z.read(destino).decode('utf-8', 'replace')
            except KeyError:
                continue
            relaciones = _rels(z, destino)
            for ancla in re.finditer(r'<xdr:(?:twoCellAnchor|oneCellAnchor|absoluteAnchor)\b.*?'
                                     r'</xdr:(?:twoCellAnchor|oneCellAnchor|absoluteAnchor)>', dibujo, re.S):
                bloque = ancla.group(0)
                grafico = re.search(r'<c:chart\b[^>]*r:id="(rId\d+)"', bloque)
                if not grafico or grafico.group(1) not in relaciones:
                    continue
                desde = re.search(r'<xdr:from>\s*<xdr:col>(\d+)</xdr:col>.*?<xdr:row>(\d+)</xdr:row>', bloque, re.S)
                fila, columna = (int(desde.group(2)), int(desde.group(1))) if desde else (0, 0)
                salida[relaciones[grafico.group(1)]] = (hoja, fila, columna)
    return salida


def definicion_de(ubicacion, definiciones):
    """La definición de Google de ese gráfico: misma hoja y ancla más cercana."""
    if not ubicacion or not definiciones:
        return None
    hoja, fila, columna = ubicacion
    candidatas = [d for d in definiciones if graficos_definiciones.misma_hoja(d.get('hoja'), hoja)]
    if not candidatas:
        return None
    distancia = lambda d: abs((d['ancla'].get('fila') or 0) - fila) + abs((d['ancla'].get('columna') or 0) - columna)
    return min(candidatas, key=distancia)


def _columna_a_numero(letras):
    numero = 0
    for letra in letras:
        numero = numero * 26 + ord(letra) - 64
    return numero


def puntos_con_valor(z, hojas, xml):
    """Índices (desde 0) de los puntos de la primera serie cuyas celdas tienen
    un número, y cuáles de ellos son distintos de cero: ([todos], [no cero])."""
    referencia = re.search(r'<c:val>\s*<c:numRef>\s*<c:f>(.*?)</c:f>', xml, re.S)
    if not referencia:
        return [], []
    texto = html.unescape(referencia.group(1)).strip()
    if '!' not in texto:
        return [], []
    hoja, rango = texto.rsplit('!', 1)
    hoja = hoja.strip().strip("'").replace("''", "'")
    m = re.match(r'\$?([A-Z]+)\$?(\d+)(?::\$?([A-Z]+)\$?(\d+))?$', rango.strip())
    pieza = hojas.get(hoja)
    if not m or not pieza:
        return [], []
    c1, f1 = _columna_a_numero(m.group(1)), int(m.group(2))
    c2, f2 = (_columna_a_numero(m.group(3)), int(m.group(4))) if m.group(3) else (c1, f1)
    try:
        datos = z.read(pieza).decode('utf-8', 'replace')
    except KeyError:
        return [], []
    valores = {}
    for celda in re.finditer(r'<c r="([A-Z]+)(\d+)"([^>]*?)(?:/>|>(.*?)</c>)', datos, re.S):
        col, fil = _columna_a_numero(celda.group(1)), int(celda.group(2))
        if not (c1 <= col <= c2 and f1 <= fil <= f2):
            continue
        if re.search(r'\bt="(?:s|str|inlineStr|e|b)"', celda.group(3)):
            continue
        valor = re.search(r'<v>([^<]*)</v>', celda.group(4) or '')
        try:
            numero = float(valor.group(1)) if valor else None
        except ValueError:
            numero = None
        if numero is not None:
            valores[(fil - f1) if c1 == c2 else (col - c1)] = numero
    todos = sorted(valores)
    return todos, [i for i in todos if valores[i] != 0]
