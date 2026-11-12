#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Que una hoja de cálculo se vea en el editor del Drive como se veía en Google.

Trabaja sobre el XML del paquete, sin abrir el libro: no toca datos, fórmulas ni
resultados guardados. Solo biblioteca estándar, porque lo usan dos sitios: el
guardado del editor (dentro del servicio) y la sincronización con Google (con
el Python del sistema). Corrige tres diferencias de interpretación (05/10/2026):

1. Regla de formato condicional «mayor que N». En Google un TEXTO nunca es
   «mayor que 0»; en el editor del Drive (y en Excel) cualquier texto lo es, así
   que las cabeceras y las columnas de texto salían pintadas con el color de la
   regla. Se convierte en una regla por fórmula que exige que la celda sea un
   número: `Y(ESNUMERO(celda); celda>N)`.

2. Relleno negro. El editor guarda el negro puro como «relleno sólido sin
   color» y luego lo pinta en blanco. Se le vuelve a escribir un negro
   explícito (01,01,01: a la vista es negro y el editor ya no lo descarta).

3. Números que no caben. Con los mismos anchos de columna, Google muestra el
   número y el editor del Drive lo cambia por «########». A los formatos de
   número (moneda, miles, porcentaje, fecha) sin «ajustar texto» se les activa
   «reducir hasta ajustar»: el número se ve entero, algo más pequeño si hace
   falta, y nadie tiene que ensanchar columnas a mano.

4. Varios renglones en una celda (20/10/2026, `saltos_linea.py`). Google
   muestra el salto de línea sin «ajustar texto»; el editor lo juntaba en un
   renglón. A esas celdas de texto se les activa «ajustar texto» y su fila
   pasa a alto automático.

Uso:  ajuste_google.py <entrada.xlsx> <salida.xlsx>
      ajustar_bytes(contenido) -> bytes   (nunca lanza: ante la duda, lo mismo que entró)
"""
import io
import logging
import re
import sys
import zipfile

import saltos_linea

log = logging.getLogger('almacen.ajuste_google')

NEGRO = 'FF010101'
_BLOQUE = re.compile(r'<conditionalFormatting([^>]*)>(.*?)</conditionalFormatting>', re.S)
_REGLA = re.compile(r'<cfRule([^>]*)>\s*<formula>\s*(-?\d+(?:\.\d+)?)\s*</formula>\s*</cfRule>', re.S)
_SIGNO = {'greaterThan': '&gt;', 'greaterThanOrEqual': '&gt;='}
# El editor, al guardar, repite cada regla en la lista de extensiones (x14) y
# al abrir usa ESA copia: hay que corregir las dos.
_BLOQUE_X14 = re.compile(r'<x14:conditionalFormatting\b[^>]*>.*?</x14:conditionalFormatting>', re.S)
_REGLA_X14 = re.compile(r'<x14:cfRule([^>]*)>\s*<xm:f>\s*(-?\d+(?:\.\d+)?)\s*</xm:f>', re.S)
_SOLIDO_SIN_COLOR = re.compile(r'<patternFill patternType="solid"\s*/>|'
                               r'<patternFill patternType="solid"\s*>\s*</patternFill>')
_NEGRO_PURO = re.compile(r'(<patternFill patternType="solid"\s*>\s*<fgColor rgb=")FF000000(")')
# Colores «del sistema» (64 texto, 65 fondo): así quedan el negro y el blanco
# cuando el libro pasó por openpyxl después de guardarse en el editor.
_DEL_SISTEMA = re.compile(r'<patternFill patternType="solid"\s*>\s*<fgColor indexed="(64|65)"\s*/>\s*'
                          r'(?:<bgColor indexed="\d+"\s*/>\s*)?</patternFill>')


def _reglas(xml):
    cambiadas = 0

    def bloque(m):
        nonlocal cambiadas
        rango = re.search(r'sqref="([^"]+)"', m.group(1))
        if not rango:
            return m.group(0)
        celda = rango.group(1).split()[0].split(':')[0].replace('$', '')

        def regla(r):
            nonlocal cambiadas
            atributos = r.group(1)
            operador = re.search(r'operator="([^"]+)"', atributos)
            if 'type="cellIs"' not in atributos or not operador or operador.group(1) not in _SIGNO:
                return r.group(0)
            atributos = re.sub(r'\s+operator="[^"]+"', '', atributos).replace('type="cellIs"', 'type="expression"')
            cambiadas += 1
            return '<cfRule%s><formula>AND(ISNUMBER(%s),%s%s%s)</formula></cfRule>' % (
                atributos, celda, celda, _SIGNO[operador.group(1)], r.group(2))
        return '<conditionalFormatting%s>%s</conditionalFormatting>' % (m.group(1), _REGLA.sub(regla, m.group(2)))

    def bloque_x14(m):
        nonlocal cambiadas
        rango = re.search(r'<xm:sqref>([^<]+)</xm:sqref>', m.group(0))
        if not rango:
            return m.group(0)
        celda = rango.group(1).split()[0].split(':')[0].replace('$', '')

        def regla(r):
            nonlocal cambiadas
            atributos = r.group(1)
            operador = re.search(r'operator="([^"]+)"', atributos)
            if 'type="cellIs"' not in atributos or not operador or operador.group(1) not in _SIGNO:
                return r.group(0)
            atributos = re.sub(r'\s+operator="[^"]+"', '', atributos).replace('type="cellIs"', 'type="expression"')
            cambiadas += 1
            return '<x14:cfRule%s><xm:f>AND(ISNUMBER(%s),%s%s%s)</xm:f>' % (
                atributos, celda, celda, _SIGNO[operador.group(1)], r.group(2))
        return _REGLA_X14.sub(regla, m.group(0))
    xml = _BLOQUE.sub(bloque, xml)
    return _BLOQUE_X14.sub(bloque_x14, xml), cambiadas


def _rellenos(xml):
    seccion = re.search(r'<fills[^>]*>.*?</fills>', xml, re.S)
    if not seccion:
        return xml, 0
    nueva, sin_color = _SOLIDO_SIN_COLOR.subn(
        '<patternFill patternType="solid"><fgColor rgb="%s"/><bgColor rgb="%s"/></patternFill>' % (NEGRO, NEGRO),
        seccion.group(0))
    nueva, puros = _NEGRO_PURO.subn(r'\g<1>%s\2' % NEGRO, nueva)
    nueva, sistema = _DEL_SISTEMA.subn(
        lambda m: '<patternFill patternType="solid"><fgColor rgb="%s"/><bgColor rgb="%s"/></patternFill>'
        % ((NEGRO, NEGRO) if m.group(1) == '64' else ('FFFFFFFF', 'FFFFFFFF')), nueva)
    return xml[:seccion.start()] + nueva + xml[seccion.end():], sin_color + puros + sistema


_XF = re.compile(r'<xf\b[^>]*?(?:/>|>.*?</xf>)', re.S)
_SIN_NUMERO = ('0', '49')                 # General y Texto: ahí no sale «####»


_TEXTO = re.compile(rb'\bt="(?:s|str|inlineStr)"')


def _formato_numerico(estilo):
    formato = re.search(r'numFmtId="(\d+)"', estilo)
    return (formato.group(1) if formato else '0') not in _SIN_NUMERO


def _uso_de_estilos(hojas, indices):
    """Para cada estilo de `indices`: (lo usa algún texto, lo usa algún número)."""
    con_texto, con_numero = set(), set()
    if not indices:
        return con_texto, con_numero
    patron = re.compile(rb'<c r="[A-Z]+\d+"[^>]*?\bs="(' + '|'.join(str(i) for i in sorted(indices)).encode()
                        + rb')"([^>]*?)(/?)>')
    for datos in hojas:
        for m in patron.finditer(datos):
            if m.group(3):
                continue                               # celda vacía: no cuenta
            (con_texto if _TEXTO.search(m.group(2)) else con_numero).add(int(m.group(1)))
    return con_texto, con_numero


def _encoger(xml, hojas=()):
    """«Reducir hasta ajustar» en los estilos de celda con formato de número.

    Un número nunca se parte en dos líneas: con «ajustar texto» también salía
    «####» (las filas de totales). Según quién use ese estilo:
      · solo números  → se cambia el ajuste por la reducción en el propio estilo;
      · texto y números (una cabecera y su total con el mismo estilo) → el texto
        conserva su ajuste y los números pasan a un estilo gemelo que reduce.
    Devuelve (estilos nuevos, cuántos estilos cambió, {estilo: gemelo}).
    """
    seccion = re.search(r'(<cellXfs[^>]*>)(.*?)(</cellXfs>)', xml, re.S)
    if not seccion:
        return xml, 0, {}
    estilos = _XF.findall(seccion.group(2))
    hojas = list(hojas)
    numericos = {i for i, e in enumerate(estilos) if _formato_numerico(e)}
    con_texto, con_numero = _uso_de_estilos(hojas, numericos)
    cambiados, gemelos = 0, {}
    # (06/10/2026) Google exporta muchas celdas de TEXTO con formato de moneda.
    # Google Sheets no tiene «reducir hasta ajustar», así que un estilo con
    # reducción que usa algún texto lo puso este mismo ajuste (versión del
    # 05/10, que no miraba quién usaba los estilos sin «ajustar texto»): el
    # texto salía diminuto. Se le quita y sus números pasan al gemelo (abajo).
    for i in sorted(numericos & con_texto):
        if 'shrinkToFit="1"' in estilos[i]:
            estilos[i] = estilos[i].replace(' shrinkToFit="1"', '', 1)
            cambiados += 1
    for i, texto in enumerate(list(estilos)):
        if i not in numericos or 'shrinkToFit="1"' in texto or i not in con_numero:
            continue                                   # ningún número lo usa: nada que reducir
        # Google escribe shrinkToFit="0" explícito: es lo mismo que no tenerlo.
        texto = re.sub(r'\s*shrinkToFit="0"', '', texto)
        if 'wrapText="1"' in texto:
            reducido = texto.replace('wrapText="1"', 'shrinkToFit="1"', 1)
        elif '<alignment' in texto:
            reducido = texto.replace('<alignment', '<alignment shrinkToFit="1"', 1)
        else:
            if 'applyAlignment' not in texto:
                texto = texto.replace('<xf ', '<xf applyAlignment="1" ', 1)
            reducido = (texto[:-2] + '><alignment shrinkToFit="1"/></xf>' if texto.endswith('/>')
                        else texto.replace('</xf>', '<alignment shrinkToFit="1"/></xf>'))
        if i in con_texto:                             # lo comparten texto y números: gemelo
            if reducido in estilos:
                gemelos[i] = estilos.index(reducido)
            else:
                estilos.append(reducido)
                gemelos[i] = len(estilos) - 1
                cambiados += 1
            continue
        estilos[i] = reducido
        cambiados += 1
    cabecera = re.sub(r'count="\d+"', 'count="%d"' % len(estilos), seccion.group(1))
    return (xml[:seccion.start(1)] + cabecera + ''.join(estilos) + xml[seccion.end(2):]), cambiados, gemelos


def _a_gemelos(datos, gemelos):
    """Pasa al estilo gemelo las celdas con NÚMERO de los estilos compartidos con texto."""
    if not gemelos:
        return datos, 0
    patron = re.compile(rb'(<c r="[A-Z]+\d+"[^>]*?\bs=")(' + '|'.join(str(i) for i in sorted(gemelos)).encode()
                        + rb')("[^>]*?)(/>|>(.*?)</c>)', re.S)
    movidas = 0

    def celda(m):
        nonlocal movidas
        cuerpo = m.group(5)
        if cuerpo is None or _TEXTO.search(m.group(3)):
            return m.group(0)
        if b'<f' in cuerpo and (b'<v></v>' in cuerpo or b'<v>' not in cuerpo) and b'&quot;' in cuerpo:
            return m.group(0)                          # fórmula sin resultado guardado que arma texto
        movidas += 1
        return m.group(1) + str(gemelos[int(m.group(2))]).encode() + m.group(3) + m.group(4)
    return patron.sub(celda, datos), movidas


def ajustar(entrada, salida):
    """De archivo (o flujo) a archivo (o flujo). Devuelve cuántas reglas, rellenos y
    estilos de número ajustó."""
    informe = {'reglas': 0, 'rellenos': 0, 'numeros': 0, 'saltos': 0}
    with zipfile.ZipFile(entrada) as origen, \
            zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as destino:
        nombres = origen.namelist()
        hojas = [n for n in nombres if re.match(r'xl/worksheets/sheet\d+\.xml$', n)]
        estilos_nuevos, gemelos, saltos = None, {}, {}
        cadenas = saltos_linea.cadenas_con_salto(
            origen.read('xl/sharedStrings.xml') if 'xl/sharedStrings.xml' in nombres else b'')
        if 'xl/styles.xml' in nombres:
            texto, n = _rellenos(origen.read('xl/styles.xml').decode('utf-8'))
            informe['rellenos'] += n
            texto, n, gemelos = _encoger(texto, (origen.read(h) for h in hojas))
            informe['numeros'] += n
            texto, n, saltos = saltos_linea.ajustar_estilos(
                texto, *saltos_linea.estilos_usados((origen.read(h) for h in hojas), cadenas))
            informe['saltos'] += n
            estilos_nuevos = texto.encode('utf-8')
        for elemento in origen.infolist():
            datos = origen.read(elemento.filename)
            if elemento.filename in hojas:
                texto, n = _reglas(datos.decode('utf-8'))
                informe['reglas'] += n
                datos, n = _a_gemelos(texto.encode('utf-8'), gemelos)
                informe['numeros'] += n
                datos, n = saltos_linea.aplicar_hoja(datos, cadenas, saltos)
                informe['saltos'] += n
            elif elemento.filename == 'xl/styles.xml' and estilos_nuevos is not None:
                datos = estilos_nuevos
            destino.writestr(elemento, datos)
    return informe


def ajustar_bytes(contenido):
    """El libro ajustado, o el mismo que entró si no hay nada que cambiar o algo falla."""
    try:
        if not contenido or contenido[:2] != b'PK':
            return contenido
        salida = io.BytesIO()
        informe = ajustar(io.BytesIO(contenido), salida)
        if not any(informe.values()):
            return contenido
        nuevo = salida.getvalue()
        zipfile.ZipFile(io.BytesIO(nuevo)).testzip()
        log.info('ajuste de vista: %d regla(s), %d relleno(s), %d formato(s) de número y %d de saltos de línea',
                 informe['reglas'], informe['rellenos'], informe['numeros'], informe['saltos'])
        return nuevo
    except Exception as excepcion:
        log.warning('ajuste de vista: no se aplicó (%s)', excepcion)
        return contenido


if __name__ == '__main__':
    print(ajustar(sys.argv[1], sys.argv[2]))
