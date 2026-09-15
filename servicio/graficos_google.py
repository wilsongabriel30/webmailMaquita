# -*- coding: utf-8 -*-
"""Arreglar los gráficos de un .xlsx bajado de Google Sheets.

Wilson, 04/09/2026: «me descargué el archivo de Google en xlsx y me distorsiona
los gráficos». Comparando el mismo archivo en Google (exportado a HTML) y en el
editor del Drive se ven tres diferencias, y las tres están en el XML que
escribe Google:

  1. **Las etiquetas salen como «0,633333333» en vez de «63%»**. Google escribe
     `<c:dLbls><c:numFmt formatCode="General" sourceLinked="1"/>`: dice «usa el
     formato de la celda» (sourceLinked) pero deja escrito «General». Google y
     Excel hacen caso a lo primero; OnlyOffice, a lo segundo. Aquí se pone el
     formato DE VERDAD de las celdas de la serie (0%, 0.00%, el que sea).
  2. **El eje llega al 120 %**. Google no escribe un máximo y su editor lo pone
     en 100 %; OnlyOffice escala solo y se pasa. Si los datos son porcentajes,
     se fija el máximo en 1 (100 %) y el mínimo en 0.
  3. **Aparece una leyenda que en Google no está**. Google la escribe aunque el
     gráfico tenga una sola serie (y entonces no dice nada: repite el título).
     Con una sola serie se quita, y el gráfico recupera ese ancho.
  4. **Los números salen ENCIMA de la barra y no dentro**. Google los pinta
     dentro, arriba del todo, en blanco sobre el color de la barra (vídeo de
     Wilson, 04/09/2026); Google no escribe `<c:dLblPos>`, así que OnlyOffice
     los saca fuera y se pisan con la barra de al lado. Se fija `inEnd` (dentro,
     al final), el texto centrado y de color según lo oscura que sea la barra.
  5. **El eje de valores sale en decimales** (0 · 0,25 · 0,5 · 0,75 · 1) en vez
     de en porcentaje: mismo enredo del `sourceLinked` que en las etiquetas,
     pero en el `<c:numFmt>` del eje.
  6. **Salen «None» donde Google no pone nada**: los ejes traen un `<c:title>`
     cuyo texto es un salto de línea, y OnlyOffice lo pinta como «None» (y, si
     el archivo se guarda desde el editor, se queda escrito ese «None»). Un
     título de eje vacío —o que ponga literalmente «None»— se quita.
  7. **Las barras salen finas.** Google tampoco escribe `<c:gapWidth>`, y sin
     él OnlyOffice deja el 150 % de hueco entre barras: quedan tan estrechas
     que el «100 %» no cabe dentro y se sale por el lado. Con el 50 % (lo que
     enseña Google) la barra es ancha y el número entra.

No se toca nada más del archivo: el resto del ZIP se copia pieza a pieza, y
solo se reescriben los `xl/charts/chartN.xml` que tengan alguno de esos tres
defectos. Los gráficos que Google exporta como IMAGEN (Google hace eso con los
tipos que el .xlsx no sabe representar) se quedan como están: son un PNG.

Con `--forzar` se aplica el aspecto de Google aunque el gráfico ya traiga esos
valores puestos. Hace falta cuando el archivo YA pasó por el editor: al guardar,
el Document Server escribe sus valores por defecto (`gapWidth 150`,
`dLblPos outEnd`), y sin forzar se respetarían por no pisar lo que haya elegido
la gente.

Se usa de dos formas:
  · a mano, sobre un archivo suelto:
        python3 graficos_google.py archivo.xlsx [salida.xlsx] [--forzar]
        python3 graficos_google.py --revisar archivo.xlsx [--forzar]
  · al SUBIR un .xlsx al Drive (api_archivos.subir), para que lo que se baja de
    Google entre ya bien. Se engancha en el endpoint de subida y NO en
    `nucleo.subir`, porque por ahí pasa también lo que guarda el editor y se
    estaría reescribiendo cada guardado (misma razón que los vínculos de datos).
"""

import html
import logging
import os
import re
import shutil
import sys
import zipfile

log = logging.getLogger('almacen.graficos')

# Formatos de porcentaje que trae el propio formato (no hace falta declararlos).
FORMATOS_FIJOS = {9: '0%', 10: '0.00%'}


# ── leer el formato de las celdas que alimentan una serie ────────────────
def _hojas_por_nombre(z):
    """{nombre de la hoja: pieza del ZIP}."""
    libro = z.read('xl/workbook.xml').decode('utf-8', 'replace')
    rels = z.read('xl/_rels/workbook.xml.rels').decode('utf-8', 'replace')
    destino = {m.group(1): m.group(2)
               for m in re.finditer(r'Id="(rId\d+)"[^>]*Target="([^"]*)"', rels)}
    salida = {}
    for m in re.finditer(r'<sheet\b[^>]*name="([^"]*)"[^>]*r:id="(rId\d+)"', libro):
        pieza = destino.get(m.group(2), '')
        if pieza:
            salida[m.group(1)] = 'xl/' + pieza.lstrip('/')
    return salida


def _formatos_de_estilo(z):
    """[formatCode] por índice de estilo (el atributo `s` de cada celda)."""
    try:
        estilos = z.read('xl/styles.xml').decode('utf-8', 'replace')
    except KeyError:
        return []
    personalizados = {int(m.group(1)): m.group(2).replace('&quot;', '"')
                      for m in re.finditer(r'<numFmt numFmtId="(\d+)" formatCode="([^"]*)"', estilos)}
    bloque = re.search(r'<cellXfs[^>]*>(.*?)</cellXfs>', estilos, re.S)
    if not bloque:
        return []
    salida = []
    for xf in re.findall(r'<xf\b[^>]*(?:/>|>.*?</xf>)', bloque.group(1), re.S):
        identificador = re.search(r'numFmtId="(\d+)"', xf)
        numero = int(identificador.group(1)) if identificador else 0
        salida.append(personalizados.get(numero) or FORMATOS_FIJOS.get(numero) or '')
    return salida


def _celdas_del_rango(referencia):
    """«'Hoja x'!$C$32:$C$41» → (hoja, [C32, C33, …]) — como mucho 40 celdas.

    Se desescapa el XML: cuando el archivo ya pasó por el editor, la referencia
    viene como `&apos;Índice…&apos;!$C$32:$C$41` y sin deshacer eso no se
    encuentra la hoja (y entonces no se sabía el formato de los números).
    """
    texto = html.unescape(str(referencia or '')).strip()
    if '!' not in texto:
        return None, []
    hoja, rango = texto.rsplit('!', 1)
    hoja = hoja.strip().strip("'").replace("''", "'")
    rango = rango.replace('$', '')
    trozos = rango.split(':')
    if len(trozos) == 1:
        return hoja, [trozos[0]]
    inicio, fin = trozos[0], trozos[1]
    m1 = re.match(r'([A-Z]+)(\d+)$', inicio)
    m2 = re.match(r'([A-Z]+)(\d+)$', fin)
    if not m1 or not m2 or m1.group(1) != m2.group(1):
        return hoja, []
    columna = m1.group(1)
    desde, hasta = int(m1.group(2)), int(m2.group(2))
    return hoja, [columna + str(f) for f in range(desde, min(hasta, desde + 39) + 1)]


def formato_de_la_serie(z, hojas, formatos, referencia):
    """El formato de número de las celdas de esa serie ('' si no se sabe)."""
    hoja, celdas = _celdas_del_rango(referencia)
    pieza = hojas.get(hoja)
    if not pieza or not celdas:
        return ''
    try:
        texto = z.read(pieza).decode('utf-8', 'replace')
    except KeyError:
        return ''
    for celda in celdas:
        m = re.search(r'<c r="%s"([^>]*)[/>]' % celda, texto)
        if not m:
            continue
        estilo = re.search(r's="(\d+)"', m.group(1))
        if not estilo:
            continue
        indice = int(estilo.group(1))
        if 0 <= indice < len(formatos) and formatos[indice]:
            return formatos[indice]
    return ''


def es_porcentaje(formato):
    return '%' in (formato or '')


# ── los tres arreglos sobre el XML de un gráfico ─────────────────────────
def etiquetas_con_formato(xml, formato):
    """Las etiquetas de datos, con el formato de la celda (y no «General»)."""
    if not formato:
        return xml, 0
    cuantas = [0]

    def cambiar(bloque):
        texto = bloque.group(0)
        nuevo, n = re.subn(r'<c:numFmt formatCode="General" sourceLinked="[01]"\s*/>',
                           '<c:numFmt formatCode="%s" sourceLinked="0"/>' % formato,
                           texto)
        cuantas[0] += n
        return nuevo

    return re.sub(r'<c:dLbls>.*?</c:dLbls>', cambiar, xml, flags=re.S), cuantas[0]


def eje_hasta_cien(xml):
    """Si los datos son porcentajes, el eje de valores va de 0 a 100 %, con las
    mismas cuatro divisiones que enseña Google (0, 25, 50, 75, 100)."""
    bloque = re.search(r'<c:valAx>.*?</c:valAx>', xml, re.S)
    if not bloque:
        return xml, 0
    texto = bloque.group(0)
    if '<c:max' in texto:
        return xml, 0
    nuevo = re.sub(r'(<c:scaling>\s*<c:orientation val="[^"]*"\s*/>)',
                   r'\1<c:max val="1"/><c:min val="0"/>', texto, count=1)
    if nuevo == texto:
        return xml, 0
    if '<c:majorUnit' not in nuevo:
        # El esquema manda: majorUnit va DESPUÉS de crossAx.
        nuevo = re.sub(r'(<c:crossAx val="\d+"\s*/>)', r'\1<c:majorUnit val="0.25"/>',
                       nuevo, count=1)
    return xml.replace(texto, nuevo), 1


def _color_de_la_serie(bloque):
    """El color de relleno de la serie («1383B1»), o '' si no lo dice."""
    m = re.search(r'<c:spPr>.*?<a:solidFill>\s*<a:srgbClr val="([0-9A-Fa-f]{6})"', bloque, re.S)
    return m.group(1).upper() if m else ''


def _texto_sobre(color):
    """Blanco sobre un color oscuro, negro sobre uno claro. La misma cuenta de
    luminancia que usa `editor-contraste.js` para las pastillas."""
    if not color:
        return 'FFFFFF'
    r, v, a = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    luz = (0.299 * r + 0.587 * v + 0.114 * a) / 255.0
    return '000000' if luz > 0.6 else 'FFFFFF'


def etiquetas_dentro(xml, forzar=False):
    """Los números, DENTRO de la barra y arriba, como los pinta Google."""
    cuantas = [0]

    def cambiar(serie):
        texto = serie.group(0)
        if '<c:dLbls>' not in texto:
            return texto
        if '<c:dLblPos' in texto:
            if not forzar or '<c:dLblPos val="inEnd"/>' in texto:
                return texto
            texto = re.sub(r'<c:dLblPos val="[^"]*"\s*/>', '<c:dLblPos val="inEnd"/>', texto)
            cuantas[0] += 1
            # sigue: falta asegurar color y centrado
        color = _texto_sobre(_color_de_la_serie(texto))
        relleno = '<a:solidFill><a:srgbClr val="%s"/></a:solidFill>' % color
        nuevo = texto
        etiquetas = re.search(r'<c:dLbls>.*?</c:dLbls>', nuevo, re.S)
        if not etiquetas:
            return texto
        bloque = etiquetas.group(0)
        arreglado = bloque
        if '<c:dLblPos' in arreglado and '<c:txPr>' in arreglado and not forzar:
            return nuevo
        if '<c:txPr>' not in arreglado:
            # Sin `txPr` no hay dónde poner el color ni el centrado: se crea.
            # En el esquema va detrás de numFmt/spPr y delante de dLblPos.
            texto_pr = ('<c:txPr><a:bodyPr/><a:lstStyle/><a:p><a:pPr lvl="0" algn="ctr">'
                        '<a:defRPr>%s</a:defRPr></a:pPr></a:p></c:txPr>' % relleno)
            if '<c:numFmt' in arreglado:
                arreglado = re.sub(r'(<c:numFmt[^/]*/>)', r'\1' + texto_pr, arreglado, count=1)
            else:
                arreglado = arreglado.replace('<c:dLbls>', '<c:dLbls>' + texto_pr, 1)
        else:
            # El color del número, dentro del <a:defRPr> que ya trae.
            if '<a:defRPr/>' in arreglado:
                arreglado = arreglado.replace('<a:defRPr/>', '<a:defRPr>%s</a:defRPr>' % relleno, 1)
            elif '<a:defRPr' in arreglado and '<a:solidFill>' not in arreglado.split('<a:defRPr', 1)[1][:200]:
                arreglado = re.sub(r'(<a:defRPr[^>]*>)', r'\1' + relleno, arreglado, count=1)
            # Centrado en la barra (si no, OnlyOffice lo pega a la izquierda).
            arreglado = re.sub(r'<a:pPr lvl="0"(?![^>]*algn=)', '<a:pPr lvl="0" algn="ctr"', arreglado)
        # Y la posición: `dLblPos` va después de txPr y antes de showLegendKey.
        if '<c:dLblPos' not in arreglado:
            if '<c:showLegendKey' in arreglado:
                arreglado = arreglado.replace('<c:showLegendKey', '<c:dLblPos val="inEnd"/><c:showLegendKey', 1)
            else:
                arreglado = arreglado.replace('</c:dLbls>', '<c:dLblPos val="inEnd"/></c:dLbls>', 1)
        if arreglado == bloque:
            return texto
        cuantas[0] += 1
        return nuevo.replace(bloque, arreglado)

    return re.sub(r'<c:ser>.*?</c:ser>', cambiar, xml, flags=re.S), cuantas[0]


def barras_anchas(xml, hueco=50, forzar=False):
    """El hueco entre barras que enseña Google. Sin `gapWidth`, OnlyOffice usa
    el 150 % y las barras salen finísimas."""
    if '<c:barChart>' not in xml:
        return xml, 0
    if '<c:gapWidth' in xml:
        if not forzar:
            return xml, 0
        actual = re.search(r'<c:gapWidth val="(\d+)"\s*/>', xml)
        if actual and int(actual.group(1)) == hueco:
            return xml, 0
        return re.sub(r'<c:gapWidth val="\d+"\s*/>',
                      '<c:gapWidth val="%d"/>' % hueco, xml, count=1), 1
    bloque = re.search(r'<c:barChart>.*?</c:barChart>', xml, re.S)
    if not bloque:
        return xml, 0
    texto = bloque.group(0)
    # En el esquema, gapWidth va tras las series y antes de los axId.
    nuevo = re.sub(r'(<c:axId val="\d+"\s*/>)', r'<c:gapWidth val="%d"/>\1' % hueco,
                   texto, count=1)
    if nuevo == texto:
        return xml, 0
    return xml.replace(texto, nuevo), 1


def eje_en_porcentaje(xml, formato):
    """El eje de valores, con el mismo formato que los números de las barras."""
    if not es_porcentaje(formato):
        return xml, 0
    bloque = re.search(r'<c:valAx>.*?</c:valAx>', xml, re.S)
    if not bloque:
        return xml, 0
    texto = bloque.group(0)
    nuevo, n = re.subn(r'<c:numFmt formatCode="General" sourceLinked="[01]"\s*/>',
                       '<c:numFmt formatCode="%s" sourceLinked="0"/>' % formato,
                       texto, count=1)
    if not n:
        return xml, 0
    return xml.replace(texto, nuevo), 1


def sin_titulos_vacios(xml):
    """Un `<c:title>` de eje sin texto lo pinta OnlyOffice como «None»."""
    cuantos = [0]

    def limpiar(eje):
        texto = eje.group(0)
        titulo = re.search(r'<c:title>.*?</c:title>', texto, re.S)
        if not titulo:
            return texto
        letras = ''.join(re.findall(r'<a:t>(.*?)</a:t>', titulo.group(0), re.S)).strip()
        # «None» es lo que escribe el editor cuando el título venía vacío: no es
        # un título de verdad, aunque lo parezca.
        if letras and letras.lower() != 'none':
            return texto                      # tiene título de verdad: se respeta
        cuantos[0] += 1
        return texto.replace(titulo.group(0), '')

    xml = re.sub(r'<c:catAx>.*?</c:catAx>', limpiar, xml, flags=re.S)
    xml = re.sub(r'<c:valAx>.*?</c:valAx>', limpiar, xml, flags=re.S)
    return xml, cuantos[0]


def sin_leyenda_de_una(xml):
    """Con una sola serie la leyenda no dice nada y come ancho: fuera."""
    if len(re.findall(r'<c:ser>', xml)) != 1:
        return xml, 0
    nuevo, n = re.subn(r'<c:legend>.*?</c:legend>', '', xml, flags=re.S)
    return nuevo, n


def arreglar_chart(z, hojas, formatos, xml, forzar=False):
    """El XML del gráfico arreglado y qué se le hizo."""
    referencia = re.search(r'<c:val>\s*<c:numRef>\s*<c:f>(.*?)</c:f>', xml, re.S)
    formato = formato_de_la_serie(z, hojas, formatos,
                                  referencia.group(1) if referencia else '')
    hecho = {}
    xml, n = etiquetas_con_formato(xml, formato)
    if n:
        hecho['etiquetas'] = formato
    if es_porcentaje(formato):
        xml, n = eje_hasta_cien(xml)
        if n:
            hecho['eje'] = '0–100 %'
        xml, n = eje_en_porcentaje(xml, formato)
        if n:
            hecho['eje en %'] = formato
    xml, n = sin_titulos_vacios(xml)
    if n:
        hecho['titulos'] = 'sin los «None» de los ejes'
    xml, n = etiquetas_dentro(xml, forzar)
    if n:
        hecho['numeros'] = 'dentro de la barra'
    xml, n = barras_anchas(xml, forzar=forzar)
    if n:
        hecho['barras'] = 'anchas como en Google'
    xml, n = sin_leyenda_de_una(xml)
    if n:
        hecho['leyenda'] = 'quitada'
    return xml, hecho


# ── entrada pública ──────────────────────────────────────────────────────
def revisar(origen, forzar=False):
    """Qué se le haría a cada gráfico, sin tocar nada."""
    salida = {}
    with zipfile.ZipFile(origen) as z:
        hojas = _hojas_por_nombre(z)
        formatos = _formatos_de_estilo(z)
        for nombre in sorted(n for n in z.namelist()
                             if re.match(r'xl/charts/chart\d+\.xml$', n)):
            xml = z.read(nombre).decode('utf-8', 'replace')
            _, hecho = arreglar_chart(z, hojas, formatos, xml, forzar)
            salida[nombre] = hecho
    return salida


def arreglar(origen, destino, forzar=False):
    """Escribe en `destino` el archivo con los gráficos arreglados.
    Devuelve {gráfico: qué se le hizo} — vacío si no hacía falta tocar nada."""
    try:
        with zipfile.ZipFile(origen) as z:
            hojas = _hojas_por_nombre(z)
            formatos = _formatos_de_estilo(z)
            nuevos, informe = {}, {}
            for nombre in sorted(n for n in z.namelist()
                                 if re.match(r'xl/charts/chart\d+\.xml$', n)):
                xml = z.read(nombre).decode('utf-8', 'replace')
                arreglado, hecho = arreglar_chart(z, hojas, formatos, xml, forzar)
                if hecho:
                    nuevos[nombre] = arreglado
                    informe[nombre] = hecho
            if not nuevos:
                return {}
            with zipfile.ZipFile(destino, 'w', zipfile.ZIP_DEFLATED) as salida:
                for info in z.infolist():
                    if info.filename in nuevos:
                        salida.writestr(info, nuevos[info.filename].encode('utf-8'))
                    else:
                        salida.writestr(info, z.read(info.filename))
        log.info('gráficos arreglados en %s: %s', origen, informe)
        return informe
    except Exception as excepcion:
        log.warning('no se pudieron arreglar los gráficos de %s: %s', origen, excepcion)
        return {}


# Más allá de esto no compensa reescribir el ZIP durante una subida.
TAMANO_MAXIMO = 40 * 1024 ** 2
EXTENSIONES = ('.xlsx', '.xlsm')


def arreglar_en_sitio(fisica, tope=TAMANO_MAXIMO):
    """Arregla el archivo DONDE ESTÁ (subida). Devuelve el informe, o {} si no
    era una hoja, era enorme, no hacía falta o algo falló: el archivo subido se
    queda tal cual, que es lo que pasaba antes de esto."""
    temporal = None
    try:
        if not str(fisica).lower().endswith(EXTENSIONES):
            return {}
        if os.path.getsize(fisica) > tope:
            return {}
        temporal = fisica + '.graficos'
        informe = arreglar(fisica, temporal)
        if not informe:
            return {}
        shutil.copymode(fisica, temporal)
        os.replace(temporal, fisica)          # atómico: nadie ve un archivo a medias
        temporal = None
        return informe
    except Exception as excepcion:
        log.warning('gráficos de %s: no se pudo arreglar en su sitio (%s)', fisica, excepcion)
        return {}
    finally:
        if temporal:
            try:
                os.unlink(temporal)
            except OSError:
                pass


if __name__ == '__main__':
    forzar = '--forzar' in sys.argv
    argumentos = [a for a in sys.argv[1:] if a not in ('--revisar', '--forzar')]
    if not argumentos:
        print(__doc__)
        sys.exit(2)
    if '--revisar' in sys.argv:
        for grafico, hecho in revisar(argumentos[0], forzar).items():
            print('%s: %s' % (grafico, hecho or 'nada que arreglar'))
        sys.exit(0)
    entrada = argumentos[0]
    salida = argumentos[1] if len(argumentos) > 1 else entrada
    temporal = salida + '.nuevo'
    informe = arreglar(entrada, temporal, forzar)
    if not informe:
        print('No hacía falta arreglar nada.')
        sys.exit(0)
    shutil.move(temporal, salida)
    for grafico, hecho in informe.items():
        print('%s: %s' % (grafico, hecho))
