# -*- coding: utf-8 -*-
"""
Almacén — sacar UNA hoja de un libro a su propio archivo
========================================================
Copiar una pestaña a otro libro con «Mover o copiar» del editor se lleva las
fórmulas tal cual. Si esa hoja se alimentaba de otra (`='Prueba IFO'!A5`,
`ÍNDICE`, `BUSCARV`…), en el archivo nuevo la hoja de origen no existe y todo
queda en `#¿NOMBRE?`. Le pasó a las diez pestañas de provincia el 22/09/2026.

Aquí se hace bien y de una vez:

  · se parte del ARCHIVO ORIGINAL, así que la hoja llega con sus estilos, sus
    celdas combinadas, su tabla y su imagen;
  · se quedan fuera las demás hojas;
  · **las fórmulas se cambian por su último resultado**, que el propio `.xlsx`
    guarda junto a cada fórmula. No hace falta el editor ni recalcular nada: es
    literalmente «pegar solo valores».

Lo que no tenga resultado guardado (una fórmula que nunca se calculó) se queda
vacío, que es preferible a dejar un error.

Con fórmulas (28/09/2026), dos maneras (`extraer(..., que=…)`):
  · 'propias': la hoja sola e independiente; conserva sus fórmulas de cálculo
    y congela solo las que tomaban datos de otra hoja;
  · 'formulas': la hoja tal cual y, OCULTAS, las hojas de las que beben sus
    fórmulas (`hoja_dependencias`). Los nombres definidos se renumeran o se quitan, y se
retira la cadena de cálculo (numeraba las hojas del libro original).

Autoría: Equipo de Tecnología Maquita — 2026-09-22
"""
import io
import logging
import posixpath
import re
import zipfile

log = logging.getLogger('almacen.hoja_a_archivo')

RE_CELDA = re.compile(r'<c\b[^>]*?(?:/>|>.*?</c>)', re.S)


class SinLaHoja(Exception):
    """El libro no tiene una hoja con ese nombre."""


def _rels(z, parte):
    carpeta, nombre = posixpath.split(parte)
    ruta = posixpath.join(carpeta, '_rels', nombre + '.rels')
    if ruta not in z.namelist():
        return {}
    salida = {}
    for rel in re.findall(r'<Relationship\b[^>]*>', z.read(ruta).decode('utf-8')):
        id_ = re.search(r'Id="([^"]+)"', rel)
        destino = re.search(r'Target="([^"]+)"', rel)
        if id_ and destino:
            objetivo = destino.group(1)
            salida[id_.group(1)] = (objetivo.lstrip('/') if objetivo.startswith('/')
                                    else posixpath.normpath(posixpath.join(carpeta, objetivo)))
    return salida


def hojas_de(contenido):
    """Los nombres de las hojas del libro, en orden."""
    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        libro = z.read('xl/workbook.xml').decode('utf-8')
    nombres = []
    for etiqueta in re.findall(r'<sheet\b[^>]*/?>', libro):
        nombre = re.search(r'name="([^"]*)"', etiqueta)
        if nombre:
            nombres.append(nombre.group(1).replace('&amp;', '&').replace('&quot;', '"'))
    return nombres


def rango_de(contenido, nombre_hoja):
    """El rango que ocupa la hoja, para poder vincularla después.

    Se prefiere el de su TABLA (en las hojas de respuestas y en las de
    provincia es justo el bloque de datos con sus encabezados); si no tiene
    tabla, se usa todo lo que la hoja tenga escrito. Devuelve
    («A5:BB105», «A5») o None si la hoja está vacía.
    """
    import re as _re
    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        libro = z.read('xl/workbook.xml').decode('utf-8')
        rels = _rels(z, 'xl/workbook.xml')
        parte = None
        for etiqueta in _re.findall(r'<sheet\b[^>]*/?>', libro):
            nombre = _re.search(r'name="([^"]*)"', etiqueta)
            rid = _re.search(r'r:id="([^"]*)"', etiqueta)
            if nombre and rid and nombre.group(1).replace('&amp;', '&') == nombre_hoja:
                parte = rels.get(rid.group(1))
        if not parte:
            raise SinLaHoja(nombre_hoja)
        for objetivo in _rels(z, parte).values():
            if '/tables/' in objetivo and objetivo in z.namelist():
                ref = _re.search(r'\bref="([A-Z]+\d+:[A-Z]+\d+)"',
                                 z.read(objetivo).decode('utf-8'))
                if ref:
                    return ref.group(1), ref.group(1).split(':')[0]
        dimension = _re.search(r'<dimension ref="([A-Z]+\d+:[A-Z]+\d+)"',
                               z.read(parte).decode('utf-8'))
        if dimension:
            return dimension.group(1), dimension.group(1).split(':')[0]
    # Sin tabla y sin `<dimension>` (hojas recién creadas por herramientas): se
    # mide lo escrito. Es lo caro, por eso va al final.
    try:
        import openpyxl
        hoja = openpyxl.load_workbook(io.BytesIO(contenido))[nombre_hoja]
        medida = hoja.calculate_dimension()
        if ':' in medida:
            return medida, medida.split(':')[0]
    except Exception as excepcion:
        log.warning('rango de «%s»: %s', nombre_hoja, excepcion)
    return None


def _congelar(xml_hoja, congelar_formula=None):
    """Cada fórmula, cambiada por el valor que el archivo tiene guardado.

    Con `congelar_formula(texto) -> bool` solo se congelan las fórmulas para
    las que diga que sí; las demás se quedan tal cual. Las fórmulas compartidas
    (`<f t="shared" si="3"/>`, sin texto) siguen a la celda que las define.
    """
    compartidas = {}
    if congelar_formula:
        import hoja_dependencias
        # Solo las que DEFINEN la fórmula (con texto); las `<f … />` la heredan.
        for m in re.finditer(r'<f\b([^>/]*\bt="shared"[^>/]*)>([^<]+)</f>', xml_hoja):
            si = re.search(r'\bsi="(\d+)"', m.group(1))
            if si and si.group(1) not in compartidas:
                compartidas[si.group(1)] = congelar_formula(hoja_dependencias._texto(m.group(2)))

    def hay_que_congelar(texto):
        if not congelar_formula:
            return True
        f = re.search(r'<f\b([^>]*?)(?:/>|>(.*?)</f>)', texto, re.S)
        if f and f.group(2):
            import hoja_dependencias
            return congelar_formula(hoja_dependencias._texto(f.group(2)))
        si = re.search(r'\bsi="(\d+)"', f.group(1)) if f else None
        return bool(si and compartidas.get(si.group(1)))

    def celda(m):
        texto = m.group(0)
        if '<f' not in texto or not hay_que_congelar(texto):
            return texto
        # El resultado se guarda con el MISMO tipo que tenía (28/09/2026): un
        # texto «1.5» sigue siendo texto (antes pasaba a número y se veía
        # «1,5» a la derecha) y se reconoce también `<v xml:space="preserve">`,
        # que es como OnlyOffice guarda los textos con espacios (antes esas
        # celdas —«La Matriz»— quedaban vacías).
        cabecera = re.match(r'<c\b([^>]*?)/?>', texto).group(1)
        tipo = re.search(r'\st="([^"]*)"', cabecera)
        tipo = tipo.group(1) if tipo else 'n'
        base = re.sub(r'\st="[^"]*"', '', cabecera)
        inline = re.search(r'<is>.*?</is>', texto, re.S)
        if inline:
            return '<c%s t="inlineStr">%s</c>' % (base, inline.group(0))
        valor = re.search(r'<v(?:\s[^>]*)?>(.*?)</v>', texto, re.S)
        if valor is None or valor.group(1) == '':
            return '<c%s/>' % base
        crudo = valor.group(1)
        if tipo == 'str':
            # Texto: en línea, para no depender de las cadenas compartidas.
            return ('<c%s t="inlineStr"><is><t xml:space="preserve">%s</t></is></c>'
                    % (base, crudo))
        if tipo in ('s', 'b', 'e'):
            return '<c%s t="%s"><v>%s</v></c>' % (base, tipo, crudo)
        return '<c%s><v>%s</v></c>' % (base, crudo)
    return RE_CELDA.sub(celda, xml_hoja)


def _con_estado(etiqueta, estado):
    """La etiqueta <sheet> con ese `state` (None = visible)."""
    etiqueta = re.sub(r'\sstate="[^"]*"', '', etiqueta)
    if estado:
        etiqueta = re.sub(r'\s*/?>$', ' state="%s"/>' % estado, etiqueta)
    return etiqueta


def _nombres_definidos(libro, indices, conservadas):
    """Los nombres definidos que siguen teniendo sentido en el archivo nuevo.

    `indices` = {posición antigua: posición nueva} de las hojas que se quedan.
    Un nombre local (área de impresión, filas que se repiten…) se renumera; uno
    que apunta a una hoja que se va, se quita (quedaría en #¡REF!).
    """
    import hoja_dependencias
    bloque = re.search(r'<definedNames>(.*?)</definedNames>', libro, re.S)
    if not bloque:
        return libro
    todas = hojas_de_xml(libro)
    quedan = []
    for m in re.finditer(r'<definedName\b([^>]*)>(.*?)</definedName>', bloque.group(1), re.S):
        atributos, valor = m.group(1), m.group(2)
        local = re.search(r'localSheetId="(\d+)"', atributos)
        if local:
            if int(local.group(1)) not in indices:
                continue
            atributos = atributos.replace(local.group(0),
                                          'localSheetId="%d"' % indices[int(local.group(1))])
        nombradas = hoja_dependencias._hojas_nombradas(
            hoja_dependencias._texto(valor), todas)
        if nombradas - conservadas:
            continue
        quedan.append('<definedName%s>%s</definedName>' % (atributos, valor))
    nuevo = '<definedNames>%s</definedNames>' % ''.join(quedan) if quedan else ''
    return libro.replace(bloque.group(0), nuevo)


def hojas_de_xml(libro):
    return [n.replace('&amp;', '&').replace('&quot;', '"')
            for n in re.findall(r'<sheet\b[^>]*\bname="([^"]*)"', libro)]


QUE = ('valores', 'propias', 'formulas')


def extraer(contenido, nombre_hoja, que='valores'):
    """Bytes de un `.xlsx` nuevo con esa hoja.

    que='valores'  → la hoja sola, con cada fórmula cambiada por su resultado.
    que='propias'  → la hoja sola, independiente: conserva sus fórmulas de
                     cálculo (las que solo usan celdas de la propia hoja); las
                     que tomaban datos de otra hoja se quedan con su valor.
    que='formulas' → la hoja CON todas sus fórmulas, y además, ocultas, las
                     hojas de las que se alimentan (sin ellas sería `#¿NOMBRE?`).
    """
    if que not in QUE:
        raise ValueError('que=%r' % que)
    formulas = que == 'formulas'
    zin = zipfile.ZipFile(io.BytesIO(contenido))
    libro = zin.read('xl/workbook.xml').decode('utf-8')
    rels_libro = zin.read('xl/_rels/workbook.xml.rels').decode('utf-8')
    rels = _rels(zin, 'xl/workbook.xml')

    ocultas = set()
    if formulas:
        import hoja_dependencias
        datos = hoja_dependencias.leer_libro(contenido)
        if nombre_hoja not in datos['hojas']:
            raise SinLaHoja(nombre_hoja)
        ocultas = set(hoja_dependencias.dependencias(datos, nombre_hoja))
    conservadas = ocultas | {nombre_hoja}

    etiqueta_buena = parte_buena = rid_bueno = None
    fuera_partes, fuera_etiquetas = set(), []
    partes_ocultas, cambios_etiqueta, indices = set(), {}, {}
    for posicion, etiqueta in enumerate(re.findall(r'<sheet\b[^>]*/?>', libro)):
        nombre = re.search(r'name="([^"]*)"', etiqueta)
        rid = re.search(r'r:id="([^"]*)"', etiqueta)
        if not (nombre and rid):
            continue
        visible = nombre.group(1).replace('&amp;', '&').replace('&quot;', '"')
        parte = rels.get(rid.group(1))
        if visible in conservadas:
            indices[posicion] = len(indices)
        if visible == nombre_hoja:
            etiqueta_buena, parte_buena, rid_bueno = etiqueta, parte, rid.group(1)
            cambios_etiqueta[etiqueta] = _con_estado(etiqueta, None)
        elif visible in ocultas:
            if parte:
                partes_ocultas.add(parte)
            if 'veryHidden' not in etiqueta:
                cambios_etiqueta[etiqueta] = _con_estado(etiqueta, 'hidden')
        else:
            fuera_etiquetas.append(etiqueta)
            if parte:
                fuera_partes.add(parte)
                for objetivo in _rels(zin, parte).values():
                    # Las imágenes se comparten; solo se retiran hoja y tabla.
                    if '/tables/' in objetivo or objetivo.endswith('.xml') and '/drawings/' in objetivo:
                        fuera_partes.add(objetivo)
                carpeta, base = posixpath.split(parte)
                fuera_partes.add(posixpath.join(carpeta, '_rels', base + '.rels'))
    if not parte_buena:
        raise SinLaHoja(nombre_hoja)

    # La cadena de cálculo numera las hojas del libro original: con menos hojas
    # apuntaría a las equivocadas. Se quita y el programa la rehace al abrir.
    fuera_partes.add('xl/calcChain.xml')

    # Las partes de las hojas que se van, y las suyas, no viajan.
    conservar = set(zin.namelist()) - fuera_partes
    # El dibujo y la tabla de la hoja buena SÍ se quedan.
    for objetivo in _rels(zin, parte_buena).values():
        conservar.add(objetivo)

    # Nombres definidos: se renumeran o se quitan (antes de tocar las etiquetas,
    # que es con lo que se cuentan las posiciones antiguas).
    nuevo_libro = _nombres_definidos(libro, indices, conservadas)
    for etiqueta in fuera_etiquetas:
        nuevo_libro = nuevo_libro.replace(etiqueta, '')
    for antes, despues in cambios_etiqueta.items():
        nuevo_libro = nuevo_libro.replace(antes, despues)
    # Que abra en la hoja extraída (la pestaña activa era una posición del original).
    posicion_buena = next(n for v, n in indices.items()
                          if hojas_de_xml(libro)[v] == nombre_hoja) if indices else 0
    def vista(m):
        etiqueta = re.sub(r'\s(?:activeTab|firstSheet)="\d+"', '', m.group(0))
        return re.sub(r'\s*(/?>)$', r' activeTab="%d"\1' % posicion_buena, etiqueta)
    nuevo_libro = re.sub(r'<workbookView\b[^>]*>', vista, nuevo_libro, count=1)
    nuevo_libro = re.sub(r'<calcPr\b[^>]*/?>', '<calcPr calcId="0" fullCalcOnLoad="1"/>',
                         nuevo_libro, count=1)

    nuevo_rels = rels_libro
    for id_, objetivo in rels.items():
        if objetivo in fuera_partes and id_ != rid_bueno:
            nuevo_rels = re.sub(r'<Relationship\b[^>]*\bId="%s".*?/>' % re.escape(id_),
                                '', nuevo_rels, flags=re.S)
    tipos = zin.read('[Content_Types].xml').decode('utf-8')
    for parte in fuera_partes:
        tipos = tipos.replace('<Override PartName="/%s"' % parte, '<OverrideFuera PartName="/%s"' % parte)
    tipos = re.sub(r'<OverrideFuera\b[^>]*/>', '', tipos)

    salida = io.BytesIO()
    with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            if info.filename not in conservar:
                continue
            if info.filename == 'xl/workbook.xml':
                datos = nuevo_libro.encode('utf-8')
            elif info.filename == 'xl/_rels/workbook.xml.rels':
                datos = nuevo_rels.encode('utf-8')
            elif info.filename == '[Content_Types].xml':
                datos = tipos.encode('utf-8')
            elif info.filename == parte_buena and que == 'valores':
                datos = _congelar(zin.read(info.filename).decode('utf-8')).encode('utf-8')
            elif info.filename == parte_buena and que == 'propias':
                import hoja_dependencias
                libro_datos = hoja_dependencias.leer_libro(contenido)
                datos = _congelar(
                    zin.read(info.filename).decode('utf-8'),
                    lambda f: hoja_dependencias.bebe_de_otra(libro_datos, nombre_hoja, f)
                ).encode('utf-8')
            elif info.filename in partes_ocultas:
                # Una hoja oculta no puede quedar como pestaña seleccionada.
                datos = re.sub(r'\stabSelected="(?:1|true)"', '',
                               zin.read(info.filename).decode('utf-8')).encode('utf-8')
            else:
                datos = zin.read(info.filename)
            zout.writestr(info, datos)
    return salida.getvalue()
