# -*- coding: utf-8 -*-
"""
Recibir respuestas de un formulario — dónde escribir dentro de la hoja
======================================================================
La hoja de destino es de la persona: la ha diseñado a su manera (título arriba,
columnas en otro orden, totales propios). Aquí se averigua, leyendo el `.xlsx`
sin abrir el editor, dónde está su bloque de datos:

  · si la hoja tiene TABLAS, la que más encabezados comparte con el formulario;
  · si no tiene, la fila (de las 40 primeras) que más encabezados comparte, y
    las columnas que ocupa esa fila.

Devuelve lo que `encuestas_hoja_xml.anadir_filas(destino=…)` necesita, más los
encabezados y los valores de la columna «Fecha» (para no escribir dos veces la
misma respuesta: la fecha y hora de envío la identifica).

Autoría: Equipo de Tecnología Maquita — 2026-09-28
"""
import io
import re
import zipfile

import encuestas_hoja_xml as xml_mod
from encuestas_hoja_libro import normalizar

FILAS_A_MIRAR = 40
MINIMO_COINCIDENCIAS = 2


class SinDondeEscribir(Exception):
    """La hoja no existe o no tiene encabezados que se parezcan al formulario."""


def _parte_de_hoja(z, nombre_hoja):
    libro = z.read('xl/workbook.xml').decode('utf-8')
    rels = xml_mod._rels(z, 'xl/workbook.xml')
    for etiqueta in re.findall(r'<sheet\b[^>]*/?>', libro):
        nombre = re.search(r'name="([^"]*)"', etiqueta)
        rid = re.search(r'r:id="([^"]*)"', etiqueta)
        if nombre and rid and xml_mod.unescape(nombre.group(1)) == nombre_hoja:
            return rels.get(rid.group(1))
    return None


def _coincidencias(encabezados, buscados):
    normales = {normalizar(t) for t in buscados if t}
    return sum(1 for e in encabezados if e and normalizar(e) in normales)


def localizar(contenido, nombre_hoja, cabeceras_formulario):
    """Dónde van las filas nuevas en esa hoja. Lanza SinDondeEscribir."""
    z = zipfile.ZipFile(io.BytesIO(contenido))
    parte = _parte_de_hoja(z, nombre_hoja)
    if not parte or parte not in z.namelist():
        raise SinDondeEscribir('El archivo ya no tiene la hoja «%s»' % nombre_hoja)
    filas = xml_mod._filas(z.read(parte).decode('utf-8'))
    cadenas = xml_mod._cadenas(z)

    def textos(n, c1, c2):
        celdas = filas.get(n, {}).get('celdas', {})
        return [xml_mod._texto_celda(celdas[c][1], celdas[c][2], cadenas).strip()
                if c in celdas else '' for c in range(c1, c2 + 1)]

    elegido = None
    for objetivo in xml_mod._rels(z, parte).values():
        if '/tables/' not in objetivo or objetivo not in z.namelist():
            continue
        ref = re.search(r'\bref="([A-Z]+\d+:[A-Z]+\d+)"', z.read(objetivo).decode('utf-8'))
        if not ref:
            continue
        c1, f1, c2, f2 = xml_mod._rango(ref.group(1))
        puntos = _coincidencias(textos(f1, c1, c2), cabeceras_formulario)
        if puntos >= MINIMO_COINCIDENCIAS and (not elegido or puntos > elegido['puntos']):
            elegido = {'parte_tabla': objetivo, 'c1': c1, 'f1': f1, 'c2': c2, 'f2': f2,
                       'puntos': puntos}

    if not elegido:
        # Sin tabla: la fila de encabezados es la que más se parece al formulario.
        for n in sorted(filas)[:FILAS_A_MIRAR]:
            columnas = sorted(filas[n]['celdas'])
            if not columnas:
                continue
            c1, c2 = columnas[0], columnas[-1]
            puntos = _coincidencias(textos(n, c1, c2), cabeceras_formulario)
            if puntos >= MINIMO_COINCIDENCIAS and (not elegido or puntos > elegido['puntos']):
                elegido = {'parte_tabla': None, 'c1': c1, 'f1': n, 'c2': c2, 'f2': n,
                           'puntos': puntos}
    if not elegido:
        raise SinDondeEscribir(
            'La hoja «%s» no tiene encabezados que coincidan con las preguntas del '
            'formulario' % nombre_hoja)

    c1, f1, c2 = elegido['c1'], elegido['f1'], elegido['c2']
    encabezados = textos(f1, c1, c2)
    cuerpo = [textos(n, c1, c2) for n in sorted(filas) if n > f1]
    elegido.update({'parte_hoja': parte, 'encabezados': encabezados,
                    'cuerpo': [f for f in cuerpo if any(v != '' for v in f)]})
    return elegido


def fechas_presentes(lugar):
    """Instantes (al segundo) que ya están en la columna «Fecha» del bloque."""
    from datetime import datetime, timedelta
    normales = [normalizar(e) for e in lugar['encabezados']]
    if 'FECHA' not in normales:
        return None
    columna, salida = normales.index('FECHA'), set()
    for fila in lugar['cuerpo']:
        valor = fila[columna] if columna < len(fila) else ''
        try:
            momento = datetime(1899, 12, 30) + timedelta(days=float(valor))
            salida.add((momento + timedelta(milliseconds=500)).replace(microsecond=0))
        except (TypeError, ValueError):
            for formato in ('%d/%m/%Y %H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S'):
                try:
                    salida.add(datetime.strptime(str(valor).strip(), formato))
                    break
                except ValueError:
                    continue
    return salida
