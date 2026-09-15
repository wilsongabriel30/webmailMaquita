"""Pone color a los valores de las listas desplegables de un libro.

── Por qué hace falta ──
En Google, cada opción de una lista puede llevar su color y se ve como una
pastilla. Ese color **no viaja**: no está en el `.xlsx` que Google exporta (se
comprobó el 07/09/2026 en un libro con 14 listas: cero reglas de color) ni en su
exportación HTML (todas las celdas de lista salen con fondo blanco). Google solo
lo dibuja en su pantalla.

Lo que sí entiende el Drive es el **formato condicional**: «si esta celda dice
SI, píntala de verde». El editor lo lee y dibuja la pastilla de ese color. Esta
herramienta escribe justamente eso, en todas las listas del libro de una vez.

── Uso ──
    python3 colores-de-listas.py libro.xlsx --listar
    python3 colores-de-listas.py libro.xlsx salida.xlsx --auto
    python3 colores-de-listas.py libro.xlsx salida.xlsx --colores colores.json

`--auto` reparte una paleta suave (la de Google) entre los valores de cada
lista. Con `--colores` se manda un JSON `{"SI": "#b7e1cd", "NO": "#f4c7c3"}`.
"""
import json
import re
import sys
import zipfile

# La paleta suave de Google, la que usa para las pastillas.
PALETA = ['#b7e1cd', '#f4c7c3', '#fce8b2', '#c9daf8', '#d9d2e9',
          '#ead1dc', '#d0e0e3', '#fff2cc', '#d9ead3', '#e6b8af']

# Verde para el sí, rojo para el no: lo que espera cualquiera.
POR_COSTUMBRE = {
    'SI': '#b7e1cd', 'SÍ': '#b7e1cd', 'YES': '#b7e1cd', 'OK': '#b7e1cd',
    'NO': '#f4c7c3', 'N/A': '#efefef', 'NA': '#efefef',
    'EN PROCESO': '#fce8b2', 'PENDIENTE': '#fce8b2',
}


def hojas_del_libro(z):
    libro = z.read('xl/workbook.xml').decode('utf-8', 'replace')
    rels = z.read('xl/_rels/workbook.xml.rels').decode('utf-8', 'replace')
    destino = dict(re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rels))
    salida = []
    for m in re.finditer(r'<sheet[^>]*name="([^"]+)"[^>]*r:id="([^"]+)"', libro):
        ruta = 'xl/' + destino.get(m.group(2), '').lstrip('/')
        if ruta in z.namelist():
            salida.append((m.group(1), ruta))
    return salida


def listas_de(hoja_xml):
    """Las listas de la hoja: [(rangos, [valores]) …]. Solo las que traen los
       valores escritos; las que apuntan a un rango se dejan estar (sus valores
       están en otras celdas y ahí el color se pondría a mano)."""
    salida = []
    for m in re.finditer(r'<dataValidation ([^>]*type="list"[^>]*)>(.*?)</dataValidation>',
                         hoja_xml, re.S):
        sqref = re.search(r'sqref="([^"]+)"', m.group(1))
        formula = re.search(r'<formula1>(.*?)</formula1>', m.group(2), re.S)
        if not sqref or not formula:
            continue
        crudo = formula.group(1).strip()
        literal = re.match(r'^&quot;(.*)&quot;$|^"(.*)"$', crudo, re.S)
        if not literal:
            continue
        texto = literal.group(1) if literal.group(1) is not None else literal.group(2)
        # Dentro de una lista, un & se escribe entre comillas dobles
        # («G"&"astronomía»); aquí se devuelve a su forma normal.
        texto = texto.replace('&quot;&amp;&quot;', '&').replace('""&""', '&')
        valores = [v.strip() for v in texto.split(',') if v.strip()]
        if valores:
            salida.append((sqref.group(1), valores))
    return salida


def color_de(valor, i, mapa):
    if mapa and valor in mapa:
        return mapa[valor]
    de_costumbre = POR_COSTUMBRE.get(valor.strip().upper())
    if de_costumbre:
        return de_costumbre
    return PALETA[i % len(PALETA)]


def dxf_de(color):
    rgb = 'FF' + color.replace('#', '').upper()
    return ('<dxf><fill><patternFill><bgColor rgb="%s"/></patternFill></fill></dxf>' % rgb)


def escapar(texto):
    return (texto.replace('&', '&amp;').replace('<', '&lt;')
                 .replace('>', '&gt;').replace('"', '&quot;'))


def main(entrada, salida, mapa, solo_listar):
    z = zipfile.ZipFile(entrada)
    piezas = {n: z.read(n) for n in z.namelist()}
    estilos = piezas['xl/styles.xml'].decode('utf-8', 'replace')

    # los formatos de color que ya hubiera
    bloque = re.search(r'<dxfs count="(\d+)">(.*?)</dxfs>', estilos, re.S)
    dxfs = re.findall(r'<dxf>.*?</dxf>', bloque.group(2), re.S) if bloque else []

    nuevas, resumen = {}, []
    for nombre, ruta in hojas_del_libro(z):
        hoja = piezas[ruta].decode('utf-8', 'replace')
        listas = listas_de(hoja)
        if not listas:
            continue
        reglas = ''
        for rangos, valores in listas:
            for i, valor in enumerate(valores):
                color = color_de(valor, i, mapa)
                dxf = dxf_de(color)
                if dxf in dxfs:
                    indice = dxfs.index(dxf)
                else:
                    dxfs.append(dxf)
                    indice = len(dxfs) - 1
                reglas += ('<conditionalFormatting sqref="%s">'
                           '<cfRule type="cellIs" dxfId="%d" priority="%d" operator="equal">'
                           '<formula>"%s"</formula></cfRule></conditionalFormatting>'
                           % (rangos, indice, 100 + len(resumen) + i, escapar(valor)))
                resumen.append((nombre, valor, color))
        if not reglas or solo_listar:
            continue
        # las reglas van justo antes de dataValidations (o del final de la hoja)
        if '<dataValidations' in hoja:
            hoja = hoja.replace('<dataValidations', reglas + '<dataValidations', 1)
        else:
            hoja = hoja.replace('</worksheet>', reglas + '</worksheet>')
        nuevas[ruta] = hoja.encode('utf-8')

    if not resumen:
        print('no hay listas con valores escritos: nada que colorear')
        return 0

    print('colores para las pastillas:')
    ultimo = None
    for hoja, valor, color in resumen:
        if hoja != ultimo:
            print('  · %s' % hoja)
            ultimo = hoja
        print('      %-28s %s' % (valor[:28], color))
    if solo_listar:
        return 0

    estilos_nuevos = ('<dxfs count="%d">%s</dxfs>' % (len(dxfs), ''.join(dxfs)))
    if bloque:
        estilos = estilos.replace(bloque.group(0), estilos_nuevos)
    else:
        estilos = estilos.replace('</styleSheet>', estilos_nuevos + '</styleSheet>')
    nuevas['xl/styles.xml'] = estilos.encode('utf-8')

    with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as fuera:
        for nombre in z.namelist():
            fuera.writestr(nombre, nuevas.get(nombre, piezas[nombre]))
    print('listas con color: %d valores en %d hojas'
          % (len(resumen), len(set(h for h, _, _ in resumen))))
    return 0


if __name__ == '__main__':
    argumentos = [a for a in sys.argv[1:] if not a.startswith('--')]
    mapa = None
    if '--colores' in sys.argv:
        with open(sys.argv[sys.argv.index('--colores') + 1], encoding='utf-8') as f:
            mapa = json.load(f)
    sys.exit(main(argumentos[0],
                  argumentos[1] if len(argumentos) > 1 else 'salida.xlsx',
                  mapa, '--listar' in sys.argv))
