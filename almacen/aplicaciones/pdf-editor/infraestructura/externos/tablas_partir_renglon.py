# -*- coding: utf-8 -*-
"""
Un renglón del PDF que cruza una raya de columna son DOS celdas.

El generador del documento escribe a veces «15% IVA      $ 187,35» como una
sola línea de texto, aunque en el papel la etiqueta esté en una columna y el
importe en la siguiente. Si se toma esa línea como un renglón, cae entera en la
celda de su centro y el redibujado la parte en dos líneas dentro de ella.

Aquí se reparte por columnas mirando cada carácter: el pedazo que queda a la
izquierda de la raya es un renglón y el de la derecha, otro. Solo se parte
cuando en la raya hay un hueco de verdad (ningún carácter con tinta la pisa y
los dos pedazos están separados al menos un espacio): en un digitalizado la
caja del OCR roza o cruza la raya sin que eso sea otra celda, y ahí se deja
el renglón entero.
"""
import fitz

_MARGEN = 0.5


def _lineas_crudas(pagina):
    """Las líneas con sus caracteres, indexadas por su caja redondeada."""
    indice = {}
    try:
        bloques = pagina.get_text('rawdict')['blocks']
    except Exception:
        return indice
    for bloque in bloques:
        for linea in bloque.get('lines', []):
            clave = tuple(round(v, 1) for v in linea['bbox'])
            indice[clave] = linea
    return indice


def _rayas_que_cruza(rect, columnas):
    return [x for x in columnas[1:-1]
            if rect.x0 + _MARGEN < x < rect.x1 - _MARGEN]


def _caracteres(linea):
    for span in linea['spans']:
        for caracter in span.get('chars', []):
            yield span, caracter


def _hueco_limpio(linea, raya):
    """¿Ningún carácter con tinta pisa la raya y hay un espacio entre pedazos?"""
    izquierda = derecha = None
    ancho_espacio = 0.0
    for span, caracter in _caracteres(linea):
        x0, _y0, x1, _y1 = caracter['bbox']
        if caracter['c'].isspace():
            ancho_espacio = max(ancho_espacio, x1 - x0)
            continue
        if x0 < raya < x1:
            return False
        if x1 <= raya:
            izquierda = x1 if izquierda is None else max(izquierda, x1)
        else:
            derecha = x0 if derecha is None else min(derecha, x0)
    if izquierda is None or derecha is None:
        return False
    cuerpo = linea['spans'][0].get('size', 10.0) if linea['spans'] else 10.0
    # Un hueco de UN espacio es texto corrido que pasa por encima de la raya
    # (lo normal en un digitalizado); hace falta un hueco claramente mayor.
    minimo = max(2.0 * ancho_espacio, cuerpo * 0.5)
    return derecha - izquierda >= minimo


def _pedazos(linea, rayas):
    """Los caracteres agrupados por el tramo entre rayas, en orden de lectura."""
    grupos = {}
    for span, caracter in _caracteres(linea):
        x0, _y0, x1, _y1 = caracter['bbox']
        centro = (x0 + x1) / 2
        tramo = sum(1 for raya in rayas if centro > raya)
        grupos.setdefault(tramo, []).append((span, caracter))
    return [grupos[k] for k in sorted(grupos)]


def _renglon_de(pedazo, original):
    """Un renglón con la misma forma que los de `_renglones_dentro`."""
    texto = ''.join(c['c'] for _s, c in pedazo)
    if not texto.strip():
        return None
    # Sin los espacios de los extremos, que solo abren hueco entre columnas.
    while pedazo and pedazo[0][1]['c'].isspace():
        pedazo = pedazo[1:]
    while pedazo and pedazo[-1][1]['c'].isspace():
        pedazo = pedazo[:-1]
    caja = fitz.Rect(pedazo[0][1]['bbox'])
    for _s, c in pedazo[1:]:
        caja |= fitz.Rect(c['bbox'])
    spans = []
    for span, caracter in pedazo:
        if spans and spans[-1]['_origen'] is span:
            spans[-1]['text'] += caracter['c']
            spans[-1]['bbox'] = tuple(fitz.Rect(spans[-1]['bbox']) | fitz.Rect(caracter['bbox']))
            continue
        copia = {k: v for k, v in span.items() if k != 'chars'}
        copia['text'] = caracter['c']
        copia['bbox'] = tuple(caracter['bbox'])
        copia['origin'] = tuple(caracter['origin'])
        copia['_origen'] = span
        spans.append(copia)
    for s in spans:
        del s['_origen']
    return {
        'texto': texto.strip(),
        'rect': caja,
        'spans': spans,
        'base': original['base'],
    }


def partir_por_columnas(pagina, renglones, columnas):
    """Los mismos renglones, con los que cruzan una raya repartidos por celda."""
    if len(columnas) < 3:
        return renglones
    crudas = None
    resultado = []
    for renglon in renglones:
        rayas = _rayas_que_cruza(renglon['rect'], columnas)
        if not rayas:
            resultado.append(renglon)
            continue
        if crudas is None:
            crudas = _lineas_crudas(pagina)
        linea = crudas.get(tuple(round(v, 1) for v in renglon['rect']))
        if linea is None:
            resultado.append(renglon)
            continue
        limpias = [raya for raya in rayas if _hueco_limpio(linea, raya)]
        if not limpias:
            resultado.append(renglon)
            continue
        partes = [_renglon_de(p, renglon) for p in _pedazos(linea, limpias)]
        partes = [p for p in partes if p]
        resultado.extend(partes if len(partes) > 1 else [renglon])
    return resultado
