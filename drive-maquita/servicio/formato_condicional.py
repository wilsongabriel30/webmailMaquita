# -*- coding: utf-8 -*-
"""El formato condicional sobrevive al guardado del editor (30/09/2026).

EL PROBLEMA. El servidor de documentos 9.4.0-129 pierde TODAS las reglas de
formato condicional de una hoja de cálculo al guardarla (guardado normal,
autoguardado o forzado; con o sin nuestros módulos; también con un libro de
control hecho en Excel). Comprobado en la réplica del editor; es un defecto
conocido de esa versión (ONLYOFFICE/DocumentServer #3699). El Mapa general de
inversiones 2026 perdió sus 154 reglas el 29/09 a las 09:33, en la primera vez
que se guardó desde el editor; con ellas se fueron los colores «de semáforo».

QUÉ SE HACE. Cuando el editor entrega el libro guardado, antes de escribirlo
se le devuelven las reglas que tenía la versión ANTERIOR en disco: los bloques
`<conditionalFormatting>` de cada hoja (emparejadas por nombre) y los estilos
diferenciales `<dxfs>` de los que dependen. Solo se restaura en las hojas que
llegan SIN ninguna regla; si el editor conserva alguna (versiones futuras),
no se toca nada. Trabaja sobre el XML del paquete, sin openpyxl, para no
alterar nada más del archivo.

Uso: `conservar(ruta_del_archivo_anterior, bytes_del_nuevo) -> bytes`.
Nunca lanza: ante cualquier duda devuelve el nuevo tal cual.
"""
import io
import logging
import re
import zipfile

log = logging.getLogger('almacen.formato_condicional')

_RE_CF = re.compile(rb'<conditionalFormatting\b.*?</conditionalFormatting>', re.S)
_RE_DXFS = re.compile(rb'<dxfs\b[^>]*?(?:/>|>.*?</dxfs>)', re.S)
_RE_DXF = re.compile(rb'<dxf>.*?</dxf>|<dxf/>', re.S)
# Lo que, según el esquema, va DESPUÉS de conditionalFormatting en una hoja.
_SIGUIENTES = (b'<dataValidations', b'<hyperlinks', b'<printOptions', b'<pageMargins',
               b'<pageSetup', b'<headerFooter', b'<rowBreaks', b'<colBreaks',
               b'<customProperties', b'<cellWatches', b'<ignoredErrors', b'<smartTags',
               b'<drawing', b'<legacyDrawing', b'<legacyDrawingHF', b'<picture',
               b'<oleObjects', b'<controls', b'<webPublishItems', b'<tableParts',
               b'<extLst', b'</worksheet>')


def _hojas(paquete):
    """{nombre de hoja: ruta interna del XML}."""
    wb = paquete.read('xl/workbook.xml').decode('utf8', 'ignore')
    rels = paquete.read('xl/_rels/workbook.xml.rels').decode('utf8', 'ignore')
    destino = {}
    for m in re.finditer(r'<Relationship\b[^>]*>', rels):
        rid = re.search(r'Id="([^"]+)"', m.group(0))
        objetivo = re.search(r'Target="([^"]+)"', m.group(0))
        if rid and objetivo:
            ruta = objetivo.group(1).lstrip('/')
            destino[rid.group(1)] = ruta if ruta.startswith('xl/') else 'xl/' + ruta
    hojas = {}
    for m in re.finditer(r'<sheet\b[^>]*>', wb):
        nombre = re.search(r'name="([^"]*)"', m.group(0))
        rid = re.search(r'r:id="([^"]+)"', m.group(0))
        if nombre and rid and rid.group(1) in destino:
            hojas[_desescapar(nombre.group(1))] = destino[rid.group(1)]
    return hojas


def _desescapar(t):
    return (t.replace('&quot;', '"').replace('&apos;', "'").replace('&lt;', '<')
             .replace('&gt;', '>').replace('&amp;', '&'))


def _insertar_cf(xml, bloques):
    """Coloca los bloques en el sitio que marca el esquema."""
    posicion = len(xml)
    for marca in _SIGUIENTES:
        i = xml.find(marca)
        if i != -1 and i < posicion:
            posicion = i
    return xml[:posicion] + b''.join(bloques) + xml[posicion:]


def _desplazar_dxf(bloque, desplazamiento):
    if not desplazamiento:
        return bloque
    return re.sub(rb'dxfId="(\d+)"',
                  lambda m: b'dxfId="%d"' % (int(m.group(1)) + desplazamiento), bloque)


def conservar(ruta_anterior, nuevo):
    """bytes del libro nuevo con las reglas de la versión anterior repuestas."""
    try:
        with zipfile.ZipFile(ruta_anterior) as viejo, zipfile.ZipFile(io.BytesIO(nuevo)) as reciente:
            hojas_viejas, hojas_nuevas = _hojas(viejo), _hojas(reciente)
            estilos_viejos = viejo.read('xl/styles.xml')
            dxfs_viejos = _RE_DXFS.search(estilos_viejos)
            reglas_viejas = {}
            for nombre, ruta in hojas_viejas.items():
                bloques = _RE_CF.findall(viejo.read(ruta))
                if bloques:
                    reglas_viejas[nombre] = bloques
            if not reglas_viejas:
                return nuevo
            # Qué hojas llegaron sin reglas
            a_reponer = {}
            for nombre, bloques in reglas_viejas.items():
                ruta = hojas_nuevas.get(nombre)
                if not ruta:
                    continue
                if not _RE_CF.search(reciente.read(ruta)):
                    a_reponer[nombre] = bloques
            if not a_reponer:
                return nuevo
            # Estilos diferenciales: si el nuevo no tiene, van los viejos tal cual;
            # si tiene algunos, los viejos se añaden detrás y se desplazan los ids.
            estilos_nuevos = reciente.read('xl/styles.xml')
            dxfs_nuevos = _RE_DXFS.search(estilos_nuevos)
            cuantos_nuevos = len(_RE_DXF.findall(dxfs_nuevos.group(0))) if dxfs_nuevos else 0
            lista_vieja = _RE_DXF.findall(dxfs_viejos.group(0)) if dxfs_viejos else []
            desplazamiento = cuantos_nuevos
            total = cuantos_nuevos + len(lista_vieja)
            bloque_dxfs = b'<dxfs count="%d">' % total + (
                b''.join(_RE_DXF.findall(dxfs_nuevos.group(0))) if dxfs_nuevos else b''
            ) + b''.join(lista_vieja) + b'</dxfs>'
            if dxfs_nuevos:
                estilos_nuevos = estilos_nuevos[:dxfs_nuevos.start()] + bloque_dxfs + estilos_nuevos[dxfs_nuevos.end():]
            else:
                # va antes de tableStyles / colors / extLst, o al final
                pos = len(estilos_nuevos)
                for marca in (b'<tableStyles', b'<colors', b'<extLst', b'</styleSheet>'):
                    i = estilos_nuevos.find(marca)
                    if i != -1 and i < pos:
                        pos = i
                estilos_nuevos = estilos_nuevos[:pos] + bloque_dxfs + estilos_nuevos[pos:]

            salida = io.BytesIO()
            with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as destino:
                for info in reciente.infolist():
                    datos = reciente.read(info.filename)
                    if info.filename == 'xl/styles.xml':
                        datos = estilos_nuevos
                    else:
                        for nombre, ruta in hojas_nuevas.items():
                            if ruta == info.filename and nombre in a_reponer:
                                datos = _insertar_cf(
                                    datos, [_desplazar_dxf(b, desplazamiento) for b in a_reponer[nombre]])
                    destino.writestr(info, datos)
            repuestas = sum(len(b) for b in a_reponer.values())
            log.info('formato condicional repuesto: %d bloque(s) en %d hoja(s)',
                     repuestas, len(a_reponer))
            return salida.getvalue()
    except Exception as excepcion:
        log.warning('formato condicional: no se pudo reponer (%s); se guarda tal cual', excepcion)
        return nuevo
