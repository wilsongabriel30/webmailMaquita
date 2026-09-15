# -*- coding: utf-8 -*-
"""Que lo descargado se vea igual FUERA del Drive (listas y colores).

Descubierto el 04/09/2026 con la réplica del editor: al guardar, el Document
Server escribe las listas desplegables y los colores condicionales SOLO como
extensión de Microsoft (`extLst` → `x14:dataValidations` y
`x14:conditionalFormattings`), aunque el archivo de origen los trajera en la
forma clásica. Excel entiende esa extensión; **Google Sheets y LibreOffice la
ignoran**, así que el archivo descargado se abría sin listas y sin colores: «no
preserva los datos».

Aquí se hace la traducción de vuelta: al descargar un .xlsx se pasa lo que está
en la extensión a la forma clásica —la que entiende todo el mundo— y se quita
de la extensión para no dejarlo duplicado. No se toca nada más del archivo: el
resto del ZIP se copia byte a byte.

Alcance a propósito: solo las reglas que la forma clásica sabe expresar, que
son justo las que crea el panel del Drive:
  · listas de valores escritos («Alta,Media,Baja») y listas por rango,
  · colores por valor (`cellIs` con relleno), que van a `<dxfs>` de styles.xml.
Lo que no encaje se deja como está, en la extensión: nunca se pierde nada.

Nunca lanza: si algo no cuadra, se entrega el archivo original tal cual.
"""

import logging
import os
import re
import tempfile
import zipfile

log = logging.getLogger('almacen.compatibilidad')

# Más allá de esto no compensa reescribir el ZIP en una descarga.
TAMANO_MAXIMO = 80 * 1024 ** 2

_EXT_DV = '{CCE6A557-97BC-4b89-ADB6-D9C93CAAB3DF}'
_EXT_CF = '{78C0D931-6437-407d-A8EE-F0AAD7539E65}'

# Dónde entra cada bloque en el orden que exige el esquema de la hoja:
# … conditionalFormatting, dataValidations, hyperlinks, printOptions, pageMargins …
_ANTES_DE = ('<hyperlinks', '<printOptions', '<pageMargins', '<pageSetup',
             '<headerFooter', '<drawing', '<legacyDrawing', '<tableParts',
             '<extLst', '</worksheet>')


def _sin_prefijo(texto: str) -> str:
    """Quita los prefijos de la extensión: x14:cfRule → cfRule, xm:f → formula."""
    texto = texto.replace('<xm:f>', '<formula>').replace('</xm:f>', '</formula>')
    texto = re.sub(r'</?x14:', lambda m: m.group(0).replace('x14:', ''), texto)
    texto = re.sub(r'\sxmlns:x(m|14)="[^"]*"', '', texto)
    return texto


def _punto_de_insercion(hoja: str) -> int:
    for marca in _ANTES_DE:
        pos = hoja.find(marca)
        if pos != -1:
            return pos
    return len(hoja)


# ── listas desplegables ──────────────────────────────────────────────────
def _validaciones(hoja: str):
    """(hoja sin la extensión, XML clásico de las validaciones o '')."""
    bloque = re.search(r'<ext uri="%s"[^>]*>(.*?)</ext>' % re.escape(_EXT_DV),
                       hoja, re.S)
    if not bloque:
        return hoja, ''
    piezas = re.findall(r'<x14:dataValidation\b(.*?)</x14:dataValidation>',
                        bloque.group(1), re.S)
    clasicas = []
    for pieza in piezas:
        atributos, resto = pieza.split('>', 1)
        sqref = re.search(r'<xm:sqref>(.*?)</xm:sqref>', resto, re.S)
        formula = re.search(r'<x14:formula1>\s*<xm:f>(.*?)</xm:f>', resto, re.S)
        if not sqref or not formula:
            return hoja, ''          # algo que no sabemos traducir: no se toca
        atributos = re.sub(r'\sxr:uid="[^"]*"', '', atributos)
        # `showDropDown="1"` significa, en el formato de Excel, ESCONDER la
        # flechita. El Drive dibuja la suya propia, pero fuera del Drive la
        # gente necesita la del programa: se entrega siempre visible.
        atributos = re.sub(r'\sshowDropDown="[^"]*"', '', atributos)
        clasicas.append('<dataValidation%s showDropDown="0" sqref="%s">'
                        '<formula1>%s</formula1></dataValidation>'
                        % (atributos, sqref.group(1), formula.group(1)))
    if not clasicas:
        return hoja, ''
    hoja = hoja.replace(bloque.group(0), '')
    return hoja, ('<dataValidations count="%d">%s</dataValidations>'
                  % (len(clasicas), ''.join(clasicas)))


# ── colores por valor (formato condicional) ──────────────────────────────
def _colores(hoja: str, siguiente_dxf: int):
    """(hoja sin la extensión, XML clásico, [dxf nuevos para styles.xml])."""
    bloque = re.search(r'<ext uri="%s"[^>]*>(.*?)</ext>' % re.escape(_EXT_CF),
                       hoja, re.S)
    if not bloque:
        return hoja, '', []
    piezas = re.findall(r'<x14:conditionalFormatting\b.*?</x14:conditionalFormatting>',
                        bloque.group(1), re.S)
    clasicas, dxfs = [], []
    for pieza in piezas:
        sqref = re.search(r'<xm:sqref>(.*?)</xm:sqref>', pieza, re.S)
        regla = re.search(r'<x14:cfRule\b(.*?)</x14:cfRule>', pieza, re.S)
        if not sqref or not regla:
            return hoja, '', []
        atributos, cuerpo = regla.group(1).split('>', 1)
        formato = re.search(r'<x14:dxf>(.*?)</x14:dxf>', cuerpo, re.S)
        if not formato:
            return hoja, '', []
        dxfs.append('<dxf>%s</dxf>' % _sin_prefijo(formato.group(1)))
        cuerpo = re.sub(r'<x14:dxf>.*?</x14:dxf>', '', cuerpo, flags=re.S)
        atributos = re.sub(r'\sid="[^"]*"', '', atributos)
        clasicas.append('<conditionalFormatting sqref="%s"><cfRule%s dxfId="%d">'
                        '%s</cfRule></conditionalFormatting>'
                        % (sqref.group(1), atributos,
                           siguiente_dxf + len(dxfs) - 1,
                           _sin_prefijo(cuerpo).replace('</cfRule>', '')))
    if not clasicas:
        return hoja, '', []
    hoja = hoja.replace(bloque.group(0), '')
    return hoja, ''.join(clasicas), dxfs


def _limpiar_extlst(hoja: str) -> str:
    """Un `<extLst>` que se quedó vacío molesta a algunos programas."""
    return hoja.replace('<extLst></extLst>', '')


def _cuantos_dxf(estilos: str) -> int:
    marca = re.search(r'<dxfs count="(\d+)"', estilos)
    return int(marca.group(1)) if marca else 0


def _con_dxfs(estilos: str, nuevos) -> str:
    """Añade los formatos nuevos a `<dxfs>` de styles.xml."""
    if not nuevos:
        return estilos
    if '<dxfs' not in estilos:
        # Sin dxfs: van justo antes de <tableStyles>, que es donde toca.
        bloque = '<dxfs count="%d">%s</dxfs>' % (len(nuevos), ''.join(nuevos))
        if '<tableStyles' in estilos:
            return estilos.replace('<tableStyles', bloque + '<tableStyles', 1)
        return estilos.replace('</styleSheet>', bloque + '</styleSheet>', 1)
    cuantos = _cuantos_dxf(estilos)
    estilos = re.sub(r'<dxfs count="\d+"', '<dxfs count="%d"' % (cuantos + len(nuevos)),
                     estilos, count=1)
    if '<dxfs count="%d"/>' % (cuantos + len(nuevos)) in estilos:
        return estilos.replace('<dxfs count="%d"/>' % (cuantos + len(nuevos)),
                               '<dxfs count="%d">%s</dxfs>'
                               % (cuantos + len(nuevos), ''.join(nuevos)), 1)
    return estilos.replace('</dxfs>', ''.join(nuevos) + '</dxfs>', 1)


# ── entrada pública ──────────────────────────────────────────────────────
def arreglar_hoja(hoja: str, siguiente_dxf: int):
    """(hoja arreglada, dxf nuevos) o (None, []) si no había nada que traducir."""
    original = hoja
    hoja, colores, dxfs = _colores(hoja, siguiente_dxf)
    hoja, validaciones = _validaciones(hoja)
    if not colores and not validaciones:
        return None, []
    donde = _punto_de_insercion(hoja)
    hoja = hoja[:donde] + colores + validaciones + hoja[donde:]
    hoja = _limpiar_extlst(hoja)
    return (hoja if hoja != original else None), dxfs


def convertir(origen: str, destino: str) -> bool:
    """Escribe en `destino` una copia compatible de `origen`.

    Devuelve True si hizo falta traducir algo (y `destino` es el bueno), False
    si el archivo ya estaba bien o no se pudo tocar: entonces se entrega el
    original y no pasa nada.
    """
    try:
        with zipfile.ZipFile(origen) as z:
            nombres = z.namelist()
            hojas = [n for n in nombres if re.match(r'xl/worksheets/sheet\d+\.xml$', n)]
            if not hojas:
                return False
            estilos = ''
            if 'xl/styles.xml' in nombres:
                estilos = z.read('xl/styles.xml').decode('utf-8')
            siguiente = _cuantos_dxf(estilos)
            arregladas, nuevos_dxf = {}, []
            for nombre in hojas:
                texto = z.read(nombre).decode('utf-8')
                if _EXT_DV not in texto and _EXT_CF not in texto:
                    continue
                nueva, dxfs = arreglar_hoja(texto, siguiente + len(nuevos_dxf))
                if nueva:
                    arregladas[nombre] = nueva
                    nuevos_dxf.extend(dxfs)
            if not arregladas:
                return False
            estilos_nuevos = _con_dxfs(estilos, nuevos_dxf) if estilos else ''

            with zipfile.ZipFile(destino, 'w', zipfile.ZIP_DEFLATED) as salida:
                for info in z.infolist():
                    if info.filename in arregladas:
                        salida.writestr(info, arregladas[info.filename].encode('utf-8'))
                    elif info.filename == 'xl/styles.xml' and nuevos_dxf:
                        salida.writestr(info, estilos_nuevos.encode('utf-8'))
                    else:
                        salida.writestr(info, z.read(info.filename))
        log.info('descarga: %d hoja(s) traducidas a formato clásico (%s)',
                 len(arregladas), origen)
        return True
    except Exception as excepcion:
        log.warning('descarga: no se pudo hacer compatible %s: %s', origen, excepcion)
        return False


EXTENSIONES = ('.xlsx', '.xlsm')


def copia_compatible(fisica: str):
    """Ruta de un TEMPORAL con la copia compatible, o None si no hacía falta
    (no es una hoja, es enorme o no había nada que traducir). Quien llama es
    quien borra el temporal."""
    try:
        if not fisica.lower().endswith(EXTENSIONES):
            return None
        if os.path.getsize(fisica) > TAMANO_MAXIMO:
            return None
        temporal = tempfile.NamedTemporaryFile(prefix='almacen_compat_',
                                               suffix='.xlsx', delete=False)
        temporal.close()
        if convertir(fisica, temporal.name):
            return temporal.name
        os.unlink(temporal.name)
        return None
    except Exception as excepcion:
        log.warning('descarga: copia compatible de %s: %s', fisica, excepcion)
        return None
