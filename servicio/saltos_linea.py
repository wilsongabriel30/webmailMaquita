#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Textos con varios renglones en la misma celda, como se ven en Google (20/10/2026).

Google Sheets dibuja el salto de línea de una celda (Alt+Intro) aunque la celda
no tenga «ajustar texto», y agranda la fila. Al exportar a .xlsx esas celdas
salen sin `wrapText`, así que el editor del Drive (igual que Excel) junta todo
en un solo renglón y hay que entrar a la celda para ver el resto.

Se activa «ajustar texto» solo en las celdas de TEXTO que tienen un salto de
línea, con un estilo gemelo cuando el estilo lo comparten otras celdas (para
no cambiar cómo se ven las demás). El alto que trae Google para esa fila es el
de los renglones explícitos; con «ajustar texto» un renglón largo se parte y ya
no cabe, así que la fila pasa a alto automático (el editor la mide al abrir).
Solo se toca la fila donde se acaba de activar el ajuste: en los guardados
siguientes la celda ya lo tiene y un alto puesto a mano se respeta.
Trabaja sobre el XML, sin tocar datos. Solo biblioteca estándar: lo usa
ajuste_google.py.
"""
import re

_XF = re.compile(r'<xf\b[^>]*?(?:/>|>.*?</xf>)', re.S)
_SI = re.compile(rb'<si>(.*?)</si>|<si/>', re.S)
_SALTO = re.compile(rb'\n|&#10;|&#xA;|&#xa;')
_CELDA = re.compile(rb'(<c r="[A-Z]+\d+")([^>]*?)(/>|>(.*?)</c>)', re.S)
_ESTILO = re.compile(rb'\bs="(\d+)"')
_VALOR = re.compile(rb'<v>(\d+)</v>')
_FILA = re.compile(rb'(<row\b[^>]*?)(/>|>(.*?)</row>)', re.S)


def cadenas_con_salto(compartidas):
    """Índices de sharedStrings.xml cuyo texto tiene un salto de línea."""
    if not compartidas:
        return set()
    return {i for i, m in enumerate(_SI.finditer(compartidas)) if m.group(1) and _SALTO.search(m.group(1))}


def _con_salto(atributos, cuerpo, indices):
    if cuerpo is None:
        return False
    if b't="s"' in atributos:
        valor = _VALOR.search(cuerpo)
        return bool(valor) and int(valor.group(1)) in indices
    if b't="inlineStr"' in atributos or b't="str"' in atributos:
        return bool(_SALTO.search(re.sub(rb'<f\b.*?(?:/>|</f>)', b'', cuerpo, flags=re.S)))
    return False


def estilos_usados(hojas, indices):
    """(estilos de las celdas con salto, estilos de las demás celdas)."""
    con_salto, otros = set(), set()
    for datos in hojas:
        for m in _CELDA.finditer(datos):
            estilo = _ESTILO.search(m.group(2))
            numero = int(estilo.group(1)) if estilo else 0
            (con_salto if _con_salto(m.group(2), m.group(4), indices) else otros).add(numero)
    return con_salto, otros


def _ajustado(estilo):
    estilo = re.sub(r'\s*shrinkToFit="[01]"', '', estilo)
    estilo = re.sub(r'\s*wrapText="0"', '', estilo)
    if '<alignment' in estilo:
        return estilo.replace('<alignment', '<alignment wrapText="1"', 1)
    if 'applyAlignment' not in estilo:
        estilo = estilo.replace('<xf ', '<xf applyAlignment="1" ', 1)
    return (estilo[:-2] + '><alignment wrapText="1"/></xf>' if estilo.endswith('/>')
            else estilo.replace('</xf>', '<alignment wrapText="1"/></xf>'))


def ajustar_estilos(xml, con_salto, otros):
    """Activa «ajustar texto» en los estilos de `con_salto`. Devuelve
    (estilos nuevos, cuántos cambió, {estilo: estilo con ajuste} de las celdas con salto)."""
    seccion = re.search(r'(<cellXfs[^>]*>)(.*?)(</cellXfs>)', xml, re.S)
    if not seccion or not con_salto:
        return xml, 0, {}
    estilos = _XF.findall(seccion.group(2))
    cambios = {}
    for i in sorted(con_salto):
        if i >= len(estilos) or 'wrapText="1"' in estilos[i]:
            continue
        nuevo = _ajustado(estilos[i])
        if i not in otros:                     # solo lo usan celdas con salto: se cambia en el sitio
            estilos[i] = nuevo
            cambios[i] = i
        elif nuevo in estilos:
            cambios[i] = estilos.index(nuevo)
        else:
            estilos.append(nuevo)
            cambios[i] = len(estilos) - 1
    if not cambios:
        return xml, 0, {}
    cabecera = re.sub(r'count="\d+"', 'count="%d"' % len(estilos), seccion.group(1))
    return xml[:seccion.start(1)] + cabecera + ''.join(estilos) + xml[seccion.end(2):], len(cambios), cambios


def aplicar_hoja(datos, indices, cambios):
    """Pasa las celdas con salto a su estilo con «ajustar texto» y deja su fila
    con alto automático. Devuelve (hoja, cuántas celdas)."""
    if not cambios:
        return datos, 0
    movidas = 0

    def celda(m):
        nonlocal movidas
        atributos = m.group(2)
        estilo = _ESTILO.search(atributos)
        numero = int(estilo.group(1)) if estilo else 0
        if numero not in cambios or not _con_salto(atributos, m.group(4), indices):
            return m.group(0)
        movidas += 1
        nuevo = str(cambios[numero]).encode()
        atributos = (atributos[:estilo.start(1)] + nuevo + atributos[estilo.end(1):] if estilo
                     else atributos + b' s="' + nuevo + b'"')
        return m.group(1) + atributos + m.group(3)

    def fila(m):
        if m.group(3) is None:
            return m.group(0)
        antes = movidas
        cuerpo = _CELDA.sub(celda, m.group(3))
        if movidas == antes:
            return m.group(0)
        cabecera = re.sub(rb'\s*customHeight="[01]"', b'', m.group(1))
        # Sin «ht» la fila tomaría el alto fijo de la hoja (sheetFormatPr customHeight).
        if b' ht=' not in cabecera:
            cabecera += b' customHeight="0"'
        return cabecera + b'>' + cuerpo + b'</row>'
    return _FILA.sub(fila, datos), movidas
