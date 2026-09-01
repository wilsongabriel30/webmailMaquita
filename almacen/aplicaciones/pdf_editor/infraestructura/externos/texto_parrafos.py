# -*- coding: utf-8 -*-
"""
El texto extraído debe salir por PÁRRAFOS, no renglón a renglón.

`page.get_text()` devuelve una línea por cada renglón del papel: un párrafo de
seis renglones llegaba como seis líneas sueltas y, al pegarlo en Word o en un
correo, había que volver a juntarlas a mano. Aquí se reconstruyen los párrafos:

- Los renglones de un mismo bloque de texto se unen con un espacio.
- Una palabra cortada con guion al final del renglón («docu-» / «mento») se
  vuelve a juntar.
- Un párrafo nuevo empieza cuando hay un salto vertical grande, una sangría,
  o el renglón anterior acabó corto (menos del 70 % del ancho del bloque) y
  con punto final.
- Los bloques se separan con una línea en blanco.

`reflujar_texto` hace lo mismo sobre texto plano (el que devuelve el OCR),
solo con pistas del propio texto: puntuación final, mayúscula inicial y las
líneas en blanco que ya vengan.
"""
import re

_FIN_DE_FRASE = ('.', ':', ';', '!', '?', '»', '"', ')')
_LISTA = re.compile(r'^(\s*)([-•·*–]|\d{1,3}[.)]|[a-zA-Z][.)])\s+')


def _juntar(parrafos):
    """Párrafos separados por línea en blanco; los elementos de una lista, solo
    por un salto, para que la lista se lea como tal."""
    salida = ''
    for parrafo in parrafos:
        if not salida:
            salida = parrafo
        elif _LISTA.match(parrafo) and _LISTA.match(salida.rsplit('\n', 1)[-1]):
            salida += '\n' + parrafo
        else:
            salida += '\n\n' + parrafo
    return salida


def _unir(acumulado, pedazo):
    """Une dos renglones de un mismo párrafo, resolviendo el guion de corte."""
    if not acumulado:
        return pedazo
    if acumulado.endswith('-') and len(acumulado) > 1 and acumulado[-2].isalpha() \
            and pedazo[:1].islower():
        return acumulado[:-1] + pedazo
    return acumulado + ' ' + pedazo


def _es_parrafo_nuevo(anterior, linea, ancho_bloque, interlineado):
    """¿Este renglón arranca un párrafo distinto del anterior?"""
    if anterior is None:
        return True
    salto = linea['y0'] - anterior['y1']
    if interlineado and salto > interlineado * 0.9:
        return True
    if linea['x0'] - anterior['x0'] > linea['cuerpo'] * 1.2:
        return True          # sangría de primera línea
    if _LISTA.match(linea['texto']):
        return True          # viñeta o numeración
    # Un renglón corto (no llega al 75 % del ancho de la columna) es el último
    # de su párrafo —en texto justificado solo el último queda corto— o una
    # línea suelta (título, «Proponente: …», «Fecha: …»). Se cierra ahí, salvo
    # que lo siguiente empiece en minúscula, que es continuación a ojos vista.
    corto = ancho_bloque and (anterior['x1'] - anterior['x0']) < ancho_bloque * 0.75
    if corto:
        siguiente = linea['texto'].lstrip()[:1]
        if anterior['texto'].rstrip().endswith(_FIN_DE_FRASE) or not siguiente.islower():
            return True
    return False


def _lineas_de(bloque):
    lineas = []
    for linea in bloque.get('lines', []):
        spans = [s for s in linea['spans'] if s['text'].strip()]
        if not spans:
            continue
        # Dos spans seguidos con hueco físico entre ellos llevan un espacio
        # aunque el PDF no lo traiga («sanación|dirigido»); si están pegados
        # (un importe partido en pedazos, «$ 12|49|,00»), no.
        texto = ''
        x_fin = None
        for s in spans:
            if x_fin is not None and s['bbox'][0] - x_fin > s.get('size', 10.0) * 0.12 \
                    and not texto.endswith(' ') and not s['text'].startswith(' '):
                texto += ' '
            texto += s['text']
            x_fin = s['bbox'][2]
        texto = re.sub(r'\s+', ' ', texto).strip()
        x0, y0, x1, y1 = linea['bbox']
        lineas.append({'texto': texto, 'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1,
                       'cuerpo': max(s.get('size', 10.0) for s in spans)})
    return lineas


def _ancho_de_columna(lineas):
    """El ancho de un renglón lleno: el percentil 90 de los anchos, para que los
    renglones cortos (finales de párrafo, títulos) no lo achiquen."""
    anchos = sorted(l['x1'] - l['x0'] for l in lineas)
    return anchos[min(len(anchos) - 1, int(len(anchos) * 0.9))] if anchos else 0


def parrafos_de_pagina(pagina):
    """El texto de la página, párrafo a párrafo, en orden de lectura.

    Los «bloques» del PDF NO son párrafos: Word suele dejar la última línea
    corta de un párrafo en un bloque aparte, y salía como párrafo suelto
    («…debilita la cohesión» / «organizativa.»). Por eso se juntan todos los
    renglones de la página en un solo flujo y los párrafos se deciden por
    geometría: salto vertical, sangría, viñeta o renglón corto.
    """
    try:
        bloques = pagina.get_text('dict', sort=True)['blocks']
    except Exception:
        return pagina.get_text()
    lineas = []
    for bloque in bloques:
        lineas.extend(_lineas_de(bloque))
    if not lineas:
        return ''
    lineas.sort(key=lambda l: (round(l['y0'], 0), l['x0']))
    ancho = _ancho_de_columna(lineas)
    saltos = sorted(max(0.0, b['y0'] - a['y1']) for a, b in zip(lineas, lineas[1:]))
    interlineado = saltos[len(saltos) // 2] + lineas[0]['cuerpo'] if saltos else None
    parrafos, actual, anterior = [], '', None
    for linea in lineas:
        if anterior is not None and _es_parrafo_nuevo(anterior, linea, ancho, interlineado):
            parrafos.append(actual)
            actual = ''
        actual = _unir(actual, linea['texto'])
        anterior = linea
    if actual:
        parrafos.append(actual)
    return _juntar(parrafos)


def reflujar_texto(texto):
    """Párrafos a partir de texto plano renglón a renglón (salida del OCR)."""
    parrafos = []
    actual = ''
    for cruda in texto.splitlines():
        linea = re.sub(r'\s+', ' ', cruda).strip()
        if not linea:
            if actual:
                parrafos.append(actual)
                actual = ''
            continue
        empieza_parrafo = bool(_LISTA.match(linea)) or (
            actual and actual.rstrip().endswith(_FIN_DE_FRASE)
            and linea[:1].isupper() and len(actual) < 60)
        if empieza_parrafo and actual:
            parrafos.append(actual)
            actual = ''
        actual = _unir(actual, linea)
    if actual:
        parrafos.append(actual)
    return _juntar(parrafos)
