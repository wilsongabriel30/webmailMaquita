# -*- coding: utf-8 -*-
"""
Miniatura SVG de un diagrama Draw.io — Almacén Maquita.
=======================================================
Dibuja una vista previa SIMPLIFICADA del diagrama leyendo el XML del archivo
`.drawio` (mxfile): cajas, elipses y rombos con sus colores, y las flechas
como líneas entre sus extremos. Sin navegador, sin servicios externos
(embed.diagrams.net queda prohibido por la política sin CDN): puro XML → SVG.

La primera página (`<diagram>`) puede venir como XML hijo o COMPRIMIDA
(base64 + deflate crudo + URL-encode, el formato clásico de draw.io); se
soportan ambas. FAIL-SILENT: cualquier problema devuelve None y el explorador
muestra la insignia de siempre.

Autoría: Equipo de Tecnología Maquita — 2026-08-12
"""
import base64
import html
import logging
import re
import zlib
from urllib.parse import unquote
from xml.etree import ElementTree

log = logging.getLogger('almacen.miniatura_drawio')

_TAMANO_MAXIMO = 3 * 1024 * 1024   # un .drawio real no pasa de unos KB


def _xml_de_diagrama(nodo):
    """Devuelve el nodo mxGraphModel de un <diagram> (plano o comprimido)."""
    for hijo in nodo:
        if hijo.tag == 'mxGraphModel':
            return hijo
    texto = (nodo.text or '').strip()
    if not texto:
        return None
    try:
        crudo = zlib.decompress(base64.b64decode(texto), -15)
        return ElementTree.fromstring(unquote(crudo.decode('utf-8')))
    except Exception:
        return None


def _color_de(estilo, clave, defecto):
    coincidencia = re.search(clave + r'=(#[0-9a-fA-F]{3,6})', estilo or '')
    return coincidencia.group(1) if coincidencia else defecto


def svg_de_drawio(fisica: str):
    """SVG (str) con la vista simplificada de la PRIMERA página, o None."""
    try:
        with open(fisica, 'rb') as f:
            crudo = f.read(_TAMANO_MAXIMO)
        raiz = ElementTree.fromstring(crudo.decode('utf-8', errors='replace'))
        diagrama = raiz.find('.//diagram') if raiz.tag == 'mxfile' else raiz
        modelo = _xml_de_diagrama(diagrama) if diagrama is not None else None
        if modelo is None and raiz.tag == 'mxGraphModel':
            modelo = raiz
        if modelo is None:
            return None

        celdas = {}
        figuras, aristas = [], []
        for celda in modelo.iter('mxCell'):
            geometria = celda.find('mxGeometry')
            identificador = celda.get('id')
            if celda.get('vertex') == '1' and geometria is not None:
                try:
                    x = float(geometria.get('x', 0) or 0)
                    y = float(geometria.get('y', 0) or 0)
                    ancho = float(geometria.get('width', 0) or 0)
                    alto = float(geometria.get('height', 0) or 0)
                except (TypeError, ValueError):
                    continue
                if ancho <= 0 or alto <= 0:
                    continue
                figura = {
                    'x': x, 'y': y, 'w': ancho, 'h': alto,
                    'estilo': celda.get('style') or '',
                    'texto': (celda.get('value') or '').strip(),
                }
                figuras.append(figura)
                if identificador:
                    celdas[identificador] = figura
            elif celda.get('edge') == '1':
                aristas.append((celda.get('source'), celda.get('target')))

        if not figuras:
            return None

        minimo_x = min(f['x'] for f in figuras)
        minimo_y = min(f['y'] for f in figuras)
        maximo_x = max(f['x'] + f['w'] for f in figuras)
        maximo_y = max(f['y'] + f['h'] for f in figuras)
        margen = 14
        vista = (minimo_x - margen, minimo_y - margen,
                 (maximo_x - minimo_x) + 2 * margen,
                 (maximo_y - minimo_y) + 2 * margen)

        partes = []
        # Aristas primero (debajo de las figuras).
        for origen, destino in aristas:
            a, b = celdas.get(origen), celdas.get(destino)
            if not a or not b:
                continue
            partes.append(
                '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" '
                'stroke="#9aa0a6" stroke-width="1.5"/>' % (
                    a['x'] + a['w'] / 2, a['y'] + a['h'] / 2,
                    b['x'] + b['w'] / 2, b['y'] + b['h'] / 2))

        for f in figuras[:400]:   # tope defensivo
            estilo = f['estilo']
            relleno = _color_de(estilo, 'fillColor', '#dae8fc')
            if relleno.lower() == '#none' or 'fillColor=none' in estilo:
                relleno = '#ffffff'
            borde = _color_de(estilo, 'strokeColor', '#6c8ebf')
            if estilo.startswith('ellipse') or ';ellipse' in estilo:
                partes.append(
                    '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" '
                    'fill="%s" stroke="%s"/>' % (
                        f['x'] + f['w'] / 2, f['y'] + f['h'] / 2,
                        f['w'] / 2, f['h'] / 2, relleno, borde))
            elif estilo.startswith('rhombus'):
                partes.append(
                    '<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" '
                    'fill="%s" stroke="%s"/>' % (
                        f['x'] + f['w'] / 2, f['y'],
                        f['x'] + f['w'], f['y'] + f['h'] / 2,
                        f['x'] + f['w'] / 2, f['y'] + f['h'],
                        f['x'], f['y'] + f['h'] / 2, relleno, borde))
            else:
                radio = 6 if 'rounded=1' in estilo else 0
                partes.append(
                    '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" '
                    'rx="%d" fill="%s" stroke="%s"/>' % (
                        f['x'], f['y'], f['w'], f['h'], radio, relleno, borde))
            texto = re.sub(r'<[^>]+>', ' ', f['texto']).strip()
            if texto:
                tam = max(8, min(13, f['h'] * 0.3))
                partes.append(
                    '<text x="%.1f" y="%.1f" text-anchor="middle" '
                    'font-family="Segoe UI,Roboto,Arial,sans-serif" '
                    'font-size="%.1f" fill="#202124">%s</text>' % (
                        f['x'] + f['w'] / 2, f['y'] + f['h'] / 2 + tam / 3,
                        tam, html.escape(texto[:28])))

        return ('<svg xmlns="http://www.w3.org/2000/svg" '
                'viewBox="%.1f %.1f %.1f %.1f">'
                '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" '
                'fill="#ffffff"/>%s</svg>' % (
                    vista[0], vista[1], vista[2], vista[3],
                    vista[0], vista[1], vista[2], vista[3], ''.join(partes)))
    except Exception as excepcion:
        log.debug('Sin miniatura drawio para %s: %s', fisica, excepcion)
        return None
