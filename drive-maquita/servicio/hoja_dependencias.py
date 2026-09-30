# -*- coding: utf-8 -*-
"""
Almacén — de qué otras hojas depende una hoja de un libro
=========================================================
Para sacar una hoja a su propio archivo CONSERVANDO las fórmulas hay que
llevarse también las hojas de las que se alimentan (si no, en el archivo nuevo
todo queda en `#¿NOMBRE?`). Aquí se averigua cuáles son, leyendo el `.xlsx`
directamente, sin abrir el editor.

Se miran todas las fórmulas de la hoja: las de las celdas, las de las listas
desplegables y el formato condicional, y las series de sus gráficos. En ellas
se buscan tres formas de nombrar otra hoja:

  · la referencia directa: `'Prueba IFO'!A5`, `DATOS!B2:B9`;
  · la tabla de otra hoja: `Respuestas[Provincia]`;
  · un nombre definido que apunta a otra hoja: `=SUMA(Ventas2025)`.

Y se repite con las hojas encontradas, hasta que no aparezcan más: si RESUMEN
bebe de CÁLCULOS y CÁLCULOS de DATOS, hacen falta las dos.

Autoría: Equipo de Tecnología Maquita — 2026-09-28
"""
import html
import io
import posixpath
import re
import zipfile

# Dónde viven las fórmulas dentro del XML de una hoja o de un gráfico.
RE_FORMULA = re.compile(
    r'<(f|formula|formula1|formula2|c:f|xm:f)\b[^>]*>(.*?)</\1>', re.S)
RE_HOJA_ENTRE_COMILLAS = re.compile(r"'((?:[^']|'')+)'!")
RE_HOJA_SIN_COMILLAS = re.compile(r"(?<![\w.'\]])([^\W\d][\w.]*)!", re.U)
RE_PALABRA = re.compile(r'[^\W\d][\w.]*', re.U)


def _rels(z, parte):
    carpeta, nombre = posixpath.split(parte)
    ruta = posixpath.join(carpeta, '_rels', nombre + '.rels')
    if ruta not in z.namelist():
        return {}
    salida = {}
    for rel in re.findall(r'<Relationship\b[^>]*>', z.read(ruta).decode('utf-8')):
        id_ = re.search(r'Id="([^"]+)"', rel)
        destino = re.search(r'Target="([^"]+)"', rel)
        if id_ and destino and 'External' not in rel:
            objetivo = destino.group(1)
            salida[id_.group(1)] = (objetivo.lstrip('/') if objetivo.startswith('/')
                                    else posixpath.normpath(posixpath.join(carpeta, objetivo)))
    return salida


def _texto(valor):
    return html.unescape(valor or '')


def _formulas_de(z, parte):
    """Todas las fórmulas de una hoja, incluidas las de sus gráficos."""
    textos = [_texto(m.group(2)) for m in RE_FORMULA.finditer(z.read(parte).decode('utf-8'))]
    for objetivo in _rels(z, parte).values():
        if '/drawings/' not in objetivo or objetivo not in z.namelist():
            continue
        for grafico in _rels(z, objetivo).values():
            if '/charts/' in grafico and grafico in z.namelist():
                textos += [_texto(m.group(2)) for m in
                           RE_FORMULA.finditer(z.read(grafico).decode('utf-8'))]
    return textos


def _hojas_nombradas(formula, hojas):
    """Hojas del libro que aparecen escritas en la fórmula."""
    encontradas = {m.group(1).replace("''", "'") for m in RE_HOJA_ENTRE_COMILLAS.finditer(formula)}
    sin_texto = RE_HOJA_ENTRE_COMILLAS.sub(' ', re.sub(r'"[^"\n]*"', ' ', formula))
    encontradas |= {m.group(1) for m in RE_HOJA_SIN_COMILLAS.finditer(sin_texto)}
    minusculas = {h.lower(): h for h in hojas}
    return {minusculas[h.lower()] for h in encontradas if h.lower() in minusculas}


def leer_libro(contenido):
    """Lo necesario para calcular dependencias: {hojas, partes, tablas, nombres}."""
    z = zipfile.ZipFile(io.BytesIO(contenido))
    libro = z.read('xl/workbook.xml').decode('utf-8')
    rels = _rels(z, 'xl/workbook.xml')
    hojas, partes, tablas = [], {}, {}
    for etiqueta in re.findall(r'<sheet\b[^>]*/?>', libro):
        nombre = re.search(r'name="([^"]*)"', etiqueta)
        rid = re.search(r'r:id="([^"]*)"', etiqueta)
        if not (nombre and rid) or _rid_invalido(rels, rid.group(1), z):
            continue
        visible = _texto(nombre.group(1))
        hojas.append(visible)
        partes[visible] = rels[rid.group(1)]
        for objetivo in _rels(z, partes[visible]).values():
            if '/tables/' in objetivo and objetivo in z.namelist():
                xml = z.read(objetivo).decode('utf-8')
                for atributo in ('name', 'displayName'):
                    valor = re.search(r'\b%s="([^"]+)"' % atributo, xml)
                    if valor:
                        tablas[_texto(valor.group(1)).lower()] = visible
    nombres = {}
    for m in re.finditer(r'<definedName\b([^>]*)>(.*?)</definedName>', libro, re.S):
        nombre = re.search(r'name="([^"]+)"', m.group(1))
        if nombre and not nombre.group(1).startswith('_xlnm.'):
            nombres[_texto(nombre.group(1)).lower()] = _texto(m.group(2))
    return {'zip': z, 'hojas': hojas, 'partes': partes, 'tablas': tablas, 'nombres': nombres}


def _rid_invalido(rels, rid, z):
    return rid not in rels or rels[rid] not in z.namelist()


def _directas(datos, hoja):
    """Hojas que la hoja nombra en sus fórmulas (sin seguir la cadena)."""
    memoria = datos.setdefault('directas', {})
    if hoja not in memoria:
        memoria[hoja] = _buscar_directas(datos, hoja)
    return memoria[hoja]


def _buscar_directas(datos, hoja):
    hojas, tablas, nombres = datos['hojas'], datos['tablas'], datos['nombres']
    # Todas las fórmulas juntas (una por línea, sin repetir): una sola pasada de
    # búsqueda por hoja en vez de una por celda (56.000 en «prueba IFO»).
    todo = '\n'.join(set(_formulas_de(datos['zip'], datos['partes'][hoja])))
    salida = _hojas_nombradas(todo, hojas)
    if tablas or nombres:
        sin_texto = re.sub(r'"[^"\n]*"', ' ', todo)
        for palabra in {p.lower() for p in RE_PALABRA.findall(sin_texto)}:
            if palabra in tablas:
                salida.add(tablas[palabra])
            elif palabra in nombres:
                salida |= _hojas_nombradas(nombres[palabra], hojas)
    salida.discard(hoja)
    return salida


def dependencias(datos, hoja):
    """Todas las hojas que hacen falta para que las fórmulas de `hoja` sigan
    funcionando, en el orden del libro (sin incluir la propia hoja)."""
    pendientes, vistas = [hoja], {hoja}
    while pendientes:
        for otra in _directas(datos, pendientes.pop()):
            if otra not in vistas:
                vistas.add(otra)
                pendientes.append(otra)
    vistas.discard(hoja)
    return [h for h in datos['hojas'] if h in vistas]


def todas(contenido):
    """{hoja: [hojas de las que depende]} para cada hoja del libro."""
    datos = leer_libro(contenido)
    return {h: dependencias(datos, h) for h in datos['hojas']}


def bebe_de_otra(datos, hoja, formula):
    """¿La fórmula toma algo de otra hoja (u otro libro)? Para «conservar solo
    las fórmulas propias»: las que respondan que sí se quedan con su valor."""
    if re.search(r'\[\d+\]', formula):          # vínculo a otro libro: [1]Hoja!A1
        return True
    otras = [h for h in datos['hojas'] if h != hoja]
    if _hojas_nombradas(formula, otras):
        return True
    tablas, nombres = datos['tablas'], datos['nombres']
    if not (tablas or nombres):
        return False
    sin_texto = re.sub(r'"[^"\n]*"', ' ', formula)
    for palabra in {p.lower() for p in RE_PALABRA.findall(sin_texto)}:
        if tablas.get(palabra, hoja) != hoja:
            return True
        if palabra in nombres and _hojas_nombradas(nombres[palabra], otras):
            return True
    return False


def contar_formulas(contenido):
    """{hoja: número de celdas con fórmula}. Para avisar, antes de extraer, de
    que una hoja sin fórmulas sale igual con cualquier opción."""
    datos = leer_libro(contenido)
    return {h: len(re.findall(r'<f\b', datos['zip'].read(datos['partes'][h]).decode('utf-8')))
            for h in datos['hojas']}
