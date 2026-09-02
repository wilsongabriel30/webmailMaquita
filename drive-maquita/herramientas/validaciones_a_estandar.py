# -*- coding: utf-8 -*-
"""Rescatar las listas desplegables que Google guarda «escondidas» — 02/09/2026.

── El problema ──
Cuando la fuente de una lista está en OTRA hoja (`Consolidado!$L:$L`), el
formato `.xlsx` no la admite en su sección normal, así que Google y Excel la
escriben en una **extensión** (`extLst` / `x14:dataValidations`). Muchos
programas se saltan esa extensión, y la lista «desaparece».

Comprobado en BIBLIOTECA PROCESOS FORMATIVOS.xlsx: **10 listas, todas en la
extensión y ninguna en la sección normal**.

── Lo que hace este script ──
Las copia a la sección normal, donde las lee todo el mundo. El truco para que la
referencia a otra hoja quepa ahí es un **nombre definido**: se declara una vez
en el libro (`_maq_val_1` → `Consolidado!$L:$L`) y la validación usa el nombre.

La extensión se deja como está: así el archivo sigue viéndose igual en Excel y
en Google, y además funciona en el editor.

── Por qué NO se usa openpyxl ──
Porque al abrir el archivo **borra** justo estas validaciones:
«Data Validation extension is not supported and will be removed». Aquí se toca
el XML directamente: se añade lo que falta y no se reescribe nada más —fórmulas,
formatos, gráficos e imágenes quedan intactos—.

Uso:
    python3 validaciones_a_estandar.py archivo.xlsx [salida.xlsx]
    python3 validaciones_a_estandar.py --revisar archivo.xlsx
"""
import re
import shutil
import sys
import zipfile

# Dónde puede ir la sección de validaciones dentro de una hoja: el formato manda
# un orden, y tiene que quedar ANTES de la primera de estas etiquetas.
DESPUES_DE_ESTO_NO = [
    '<hyperlinks', '<printOptions', '<pageMargins', '<pageSetup',
    '<headerFooter', '<rowBreaks', '<colBreaks', '<drawing', '<legacyDrawing',
    '<tableParts', '<extLst',
]

RE_VALIDACION = re.compile(
    r'<x14:dataValidation\b(?P<atributos>[^>]*)>(?P<cuerpo>.*?)</x14:dataValidation>',
    re.S)
RE_FORMULA1 = re.compile(r'<x14:formula1>\s*<xm:f>(?P<f>.*?)</xm:f>', re.S)
RE_FORMULA2 = re.compile(r'<x14:formula2>\s*<xm:f>(?P<f>.*?)</xm:f>', re.S)
RE_SQREF = re.compile(r'<xm:sqref>(?P<r>.*?)</xm:sqref>', re.S)
RE_ATRIBUTO = re.compile(r'(\w+)="([^"]*)"')


def atributos_de(texto):
    return dict(RE_ATRIBUTO.findall(texto))


def leer_validaciones(xml):
    """Las validaciones escondidas de una hoja."""
    salida = []
    for coincidencia in RE_VALIDACION.finditer(xml):
        atributos = atributos_de(coincidencia.group('atributos'))
        cuerpo = coincidencia.group('cuerpo')
        formula1 = RE_FORMULA1.search(cuerpo)
        sqref = RE_SQREF.search(cuerpo)
        if not formula1 or not sqref:
            continue
        formula2 = RE_FORMULA2.search(cuerpo)
        salida.append({
            'tipo': atributos.get('type', 'list'),
            'permite_vacio': atributos.get('allowBlank', '1'),
            # OJO: este atributo va al revés. "0" = SE VE la flechita.
            'esconde_flecha': atributos.get('showDropDown', '0'),
            'estilo_error': atributos.get('errorStyle', 'stop'),
            'operador': atributos.get('operator', ''),
            'avisa_error': atributos.get('showErrorMessage', '1'),
            'formula1': desescapar(formula1.group('f').strip()),
            'formula2': (desescapar(formula2.group('f').strip())
                         if formula2 else ''),
            'celdas': sqref.group('r').strip(),
        })
    return salida


def escapar(texto):
    return (texto.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def desescapar(texto):
    """Lo que se lee del XML viene escapado (&quot;SI,NO&quot;). Se deja como es
    de verdad, para poder volver a escaparlo al escribirlo y no acabar con
    &amp;quot; —que rompería la lista sin decir nada—."""
    return (texto.replace('&quot;', '"').replace('&apos;', "'")
                 .replace('&lt;', '<').replace('&gt;', '>')
                 .replace('&amp;', '&'))


def necesita_nombre(formula):
    """¿La fórmula apunta a otra hoja? Entonces no cabe en la sección normal."""
    return '!' in formula


def construir_seccion(validaciones, nombres):
    """El trozo `<dataValidations>` que se añade a la hoja."""
    piezas = ['<dataValidations count="%d">' % len(validaciones)]
    for v in validaciones:
        formula = nombres.get(v['formula1'], v['formula1'])
        atributos = [
            'type="%s"' % v['tipo'],
            'allowBlank="%s"' % v['permite_vacio'],
            'showDropDown="%s"' % v['esconde_flecha'],
            'showErrorMessage="%s"' % v['avisa_error'],
            'errorStyle="%s"' % v['estilo_error'],
            'sqref="%s"' % v['celdas'],
        ]
        if v['operador']:
            atributos.append('operator="%s"' % v['operador'])
        piezas.append('<dataValidation %s>' % ' '.join(atributos))
        piezas.append('<formula1>%s</formula1>' % escapar(formula))
        if v['formula2'] and v['formula2'] != '0':
            piezas.append('<formula2>%s</formula2>' % escapar(v['formula2']))
        piezas.append('</dataValidation>')
    piezas.append('</dataValidations>')
    return ''.join(piezas)


def insertar_en_la_hoja(xml, seccion):
    """Deja la sección en su sitio: el formato exige un orden."""
    if '<dataValidations' in xml:
        return xml, False              # ya la tenía: no se toca
    for etiqueta in DESPUES_DE_ESTO_NO:
        donde = xml.find(etiqueta)
        if donde != -1:
            return xml[:donde] + seccion + xml[donde:], True
    donde = xml.rfind('</worksheet>')
    if donde == -1:
        return xml, False
    return xml[:donde] + seccion + xml[donde:], True


def poner_nombres(workbook_xml, nombres):
    """Declara los nombres en el libro: `_maq_val_1` → Consolidado!$L:$L."""
    if not nombres:
        return workbook_xml, False
    piezas = []
    for referencia, nombre in nombres.items():
        piezas.append('<definedName name="%s">%s</definedName>'
                      % (nombre, escapar(referencia)))
    nuevos = ''.join(piezas)

    if '<definedNames>' in workbook_xml:
        # Se añaden a los que ya hubiera, sin tocarlos.
        return workbook_xml.replace('<definedNames>', '<definedNames>' + nuevos, 1), True
    # Van después de <sheets> y antes de <calcPr>, que es donde toca.
    donde = workbook_xml.find('</sheets>')
    if donde == -1:
        return workbook_xml, False
    donde += len('</sheets>')
    return (workbook_xml[:donde] + '<definedNames>' + nuevos + '</definedNames>'
            + workbook_xml[donde:], True)


def revisar(ruta):
    with zipfile.ZipFile(ruta) as z:
        hojas = [n for n in z.namelist()
                 if n.startswith('xl/worksheets/sheet') and n.endswith('.xml')]
        total_escondidas = total_normales = 0
        for hoja in sorted(hojas):
            xml = z.read(hoja).decode('utf-8', 'replace')
            escondidas = leer_validaciones(xml)
            normales = xml.count('<dataValidation ')
            total_escondidas += len(escondidas)
            total_normales += normales
            print('   %-22s  normales=%-3d  escondidas=%d'
                  % (hoja.split('/')[-1], normales, len(escondidas)))
            for v in escondidas:
                fuera = ' (otra hoja)' if necesita_nombre(v['formula1']) else ''
                flecha = 'se ve' if v['esconde_flecha'] in ('0', 'false') else 'ESCONDIDA'
                print('        %-10s %-28s flechita: %s%s'
                      % (v['celdas'], v['formula1'][:28], flecha, fuera))
    print('   TOTAL: %d normales, %d escondidas' % (total_normales, total_escondidas))
    return total_escondidas


def convertir(entrada, salida):
    with zipfile.ZipFile(entrada) as z:
        contenido = {n: z.read(n) for n in z.namelist()}
        orden = z.namelist()

    # 1) Qué hay escondido, y qué fuentes necesitan un nombre.
    porHoja = {}
    fuentes = []
    for nombre in orden:
        if not (nombre.startswith('xl/worksheets/sheet') and nombre.endswith('.xml')):
            continue
        xml = contenido[nombre].decode('utf-8', 'replace')
        validaciones = leer_validaciones(xml)
        if not validaciones:
            continue
        porHoja[nombre] = validaciones
        for v in validaciones:
            if necesita_nombre(v['formula1']) and v['formula1'] not in fuentes:
                fuentes.append(v['formula1'])

    if not porHoja:
        print('   No hay validaciones escondidas: nada que rescatar.')
        return 0

    nombres = {}
    for i, referencia in enumerate(fuentes, 1):
        nombres[referencia] = '_maq_val_%d' % i

    # 2) La sección normal en cada hoja.
    cuantas = 0
    for hoja, validaciones in porHoja.items():
        xml = contenido[hoja].decode('utf-8', 'replace')
        seccion = construir_seccion(validaciones, nombres)
        xml, puesta = insertar_en_la_hoja(xml, seccion)
        if puesta:
            contenido[hoja] = xml.encode('utf-8')
            cuantas += len(validaciones)
            print('   %-22s  +%d listas rescatadas'
                  % (hoja.split('/')[-1], len(validaciones)))

    # 3) Los nombres, en el libro.
    libro = 'xl/workbook.xml'
    if libro in contenido:
        xml = contenido[libro].decode('utf-8', 'replace')
        xml, puestos = poner_nombres(xml, nombres)
        if puestos:
            contenido[libro] = xml.encode('utf-8')
            for referencia, nombre in nombres.items():
                print('   nombre %-12s → %s' % (nombre, referencia))

    # 4) Se vuelve a armar el zip, respetando el orden original.
    with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as z:
        for nombre in orden:
            z.writestr(nombre, contenido[nombre])
    print('   Guardado en: %s' % salida)
    return cuantas


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(1)
    if sys.argv[1] == '--revisar':
        for ruta in sys.argv[2:]:
            print('\n%s' % ruta)
            revisar(ruta)
    else:
        entrada = sys.argv[1]
        salida = sys.argv[2] if len(sys.argv) > 2 else entrada.replace('.xlsx', '_ok.xlsx')
        if salida == entrada:
            raise SystemExit('La salida no puede ser el mismo archivo.')
        shutil.copy(entrada, salida + '.original')
        print('\n%s' % entrada)
        convertir(entrada, salida)
