# -*- coding: utf-8 -*-
"""Sustituye en las pestañas de provincia las columnas agrupadas antiguas por
las columnas de cada pregunta, tomando TODO de la hoja «Prueba IFO».

Por qué: hasta el 22/09/2026 las pestañas traían dos columnas que ya no existen
como tales en el formulario («¿Qué tipo de mecanismos…» y «¿En qué ámbito?»).
Esas preguntas se desglosaron en ocho de Sí/No y la hoja base ya tiene una
columna por cada una (columnas 49-56).

Qué hace, pestaña por pestaña:
  · Donde estaba la columna agrupada, deja la PRIMERA del grupo e inserta a su
    derecha las demás: la columna vieja desaparece, no se conserva.
  · Cada columna que viene del formulario recibe su encabezado y sus datos
    LEÍDOS DE «Prueba IFO» (fila 4 los títulos, ÍNDICE sobre la fila que toca
    para los datos). Nada se toma del `.forma`: la única fuente es la hoja base.
  · Las columnas propias de la persona (TOTAL, DURACIÓN) no se tocan: se
    desplazan con la inserción y conservan su fórmula.

Uso:
    python provincias_columnas.py <usuario> <ruta en el Drive> [--aplicar]

Sin `--aplicar` deja el resultado en /tmp/provincias-columnas.xlsx y no toca el
Drive. Con `--aplicar` exige que nadie tenga el Excel abierto en el editor.

Autoría: Equipo de Tecnología Maquita — 2026-09-22
"""
import io
import os
import secrets
import sys
import time

sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')
sys.path.insert(0, '/home/sistemas/almacen-maquita/herramientas')

import openpyxl
import requests

import nucleo_archivos as nucleo
from api_onlyoffice import firmar_jwt, url_interna_ds, _reescribir_url_interna
from config_almacen import URL_PUBLICA
from encuestas_hoja_recalculo import CARPETA_SCRIPTS, URL_SCRIPTS

import formulas_provincias as fp
from formulas_provincias import (HOJA_BASE, FILA_CABECERAS_BASE, FILA_CABECERAS_PESTANA,
                                 EQUIVALENCIAS, letra, plano, _js)

# Columna agrupada antigua → las columnas de la base que la sustituyen, en orden.
SUSTITUCIONES = {
    '¿QUE TIPO DE MECANISMOS UTILIZA LA ORGANIZACION COMUNITARIA PARA GARANTIZAR '
    'LA TRANSPARENCIA Y LA RENDICION DE CUENTAS?': [
        'Realiza al menos 1 reunión/asamblea por año para rendición de cuentas a socios/as',
        'Pose un inventario actualizado de bienes que posee la organización comunitaria',
        'Cuenta con documentos de respaldo respecto de inversiones, ingresos, gastos.'],
    '¿EN QUE AMBITO?': [
        'Fomento productivo', 'Ecologia - Ambiente', 'Comercialización',
        'Derechos y Género', 'Servicios básicos'],
}


def columnas_de_la_base(hoja_base):
    """{título normalizado: columna} y {columna: título}, leyendo SOLO la fila 4."""
    por_nombre, por_columna = {}, {}
    for c in range(1, 120):
        valor = hoja_base.cell(row=FILA_CABECERAS_BASE, column=c).value
        if valor:
            por_nombre.setdefault(plano(valor), c)
            por_columna[c] = str(valor)
    return por_nombre, por_columna


def planear_pestana(hoja, por_nombre):
    """Qué columnas hay que insertar y cómo queda el mapa columna → columna base.

    Devuelve (inserciones, mapa, propias, ancho) con las posiciones YA
    desplazadas, es decir, tal como quedarán después de insertar.
    """
    actuales = []                       # [(título, columna base o None)]
    for c in range(1, 120):
        titulo = hoja.cell(row=FILA_CABECERAS_PESTANA, column=c).value
        if titulo is None or str(titulo).strip() == '':
            if actuales:
                break
            continue
        clave = plano(titulo)
        clave = EQUIVALENCIAS.get(clave, clave)
        actuales.append((str(titulo), por_nombre.get(clave)))

    destino, inserciones = [], []       # destino: [(columna base o None)]
    for titulo, base in actuales:
        grupo = SUSTITUCIONES.get(plano(titulo))
        if grupo:
            # La columna agrupada deja su sitio a la primera del grupo; las
            # demás se insertan justo a su derecha.
            for n, nombre in enumerate(grupo):
                destino.append(por_nombre.get(plano(nombre)))
            inserciones.append((len(destino) - len(grupo) + 1, len(grupo) - 1))
        else:
            destino.append(base)

    mapa = {i + 1: base for i, base in enumerate(destino) if base}
    propias = [i + 1 for i, base in enumerate(destino) if not base]
    return inserciones, mapa, propias, len(destino)


def datos_para_guion(hoja, hoja_base, mapa, propias, ancho):
    """La ficha que espera `formulas_provincias.guion_para`, con las columnas ya
    desplazadas. Las fórmulas propias se leen de la pestaña ANTES de insertar:
    usan referencias estructuradas, así que siguen valiendo después."""
    formulas = {}
    for columna in propias:
        for fila in range(FILA_CABECERAS_PESTANA + 1, FILA_CABECERAS_PESTANA + 101):
            valor = hoja.cell(row=fila, column=columna).value
            if isinstance(valor, str) and valor.startswith('='):
                formulas[columna] = valor
                break
    fechas = [c for c, cb in mapa.items()
              if fp._es_fecha(hoja_base.cell(row=FILA_CABECERAS_BASE + 1, column=cb))]
    ultima = FILA_CABECERAS_PESTANA
    for fila in range(FILA_CABECERAS_PESTANA + 1, hoja.max_row + 1):
        if any(hoja.cell(row=fila, column=c).value not in (None, '') for c in mapa):
            ultima = fila
    return {'mapa': mapa, 'propias': [(c, '') for c in propias], 'ultima': ultima,
            'fechas': fechas, 'formulas': formulas, 'ancho': ancho}


def guion_de_pestana(nombre, hoja, hoja_base, por_nombre, por_columna):
    inserciones, mapa, propias, ancho = planear_pestana(hoja, por_nombre)
    if not mapa:
        return '', 0
    lineas = ['var hoja = Api.GetSheet(%s);' % _js(nombre), 'if (hoja) {']
    # De derecha a izquierda: así una inserción no descuadra las siguientes.
    for columna, cuantas in sorted(inserciones, reverse=True):
        lineas.append('  hoja.GetRange("%s:%s").Insert("right");'
                      % (letra(columna), letra(columna + cuantas - 1)))
    # Los encabezados salen de la fila 4 de «Prueba IFO», no del formulario.
    for columna, columna_base in sorted(mapa.items()):
        lineas.append('  hoja.GetRange("%s%d").SetValue(%s);'
                      % (letra(columna), FILA_CABECERAS_PESTANA,
                         _js(por_columna[columna_base])))
    lineas.append('}')
    datos = datos_para_guion(hoja, hoja_base, mapa, propias, ancho)
    return '\n'.join(lineas) + '\n' + fp.guion_para(nombre, datos, None), len(inserciones)


def principal(usuario, ruta, aplicar, solo=None):
    fisica = nucleo.ruta_fisica(usuario, ruta)
    libro = openpyxl.load_workbook(fisica)
    base = libro[HOJA_BASE]
    por_nombre, por_columna = columnas_de_la_base(base)
    print('  hoja base: %d columnas en la fila %d' % (len(por_columna), FILA_CABECERAS_BASE))

    token = firmar_jwt({'u': usuario, 'r': ruta, 'uso': 'descarga',
                        'exp': int(time.time()) + 900})
    url_libro = '%s/api/almacen/onlyoffice/download?t=%s' % (URL_PUBLICA, token)
    partes = ['builder.OpenFile("%s");' % url_libro]
    for nombre in libro.sheetnames:
        if nombre == HOJA_BASE or (solo and plano(nombre) not in solo):
            continue
        guion, n = guion_de_pestana(nombre, libro[nombre], base, por_nombre, por_columna)
        if not guion.strip():
            print('  %-12s sin columnas reconocidas: se deja como está' % nombre)
            continue
        print('  %-12s %d grupos sustituidos' % (nombre, n))
        partes.append(guion)
    partes += ['Api.RecalculateAllFormulas();',
               'builder.SaveFile("xlsx", "provincias.xlsx");', 'builder.CloseFile();']

    os.makedirs(CARPETA_SCRIPTS, exist_ok=True)
    fichero = secrets.token_hex(16) + '.docbuilder'
    camino = os.path.join(CARPETA_SCRIPTS, fichero)
    open(camino, 'w', encoding='utf-8').write('\n'.join(partes) + '\n')
    os.chmod(camino, 0o644)
    print('  guion de %d líneas' % len('\n'.join(partes).splitlines()))
    try:
        cuerpo = {'async': False, 'key': 'prov' + secrets.token_hex(8),
                  'url': '%s%s/%s' % (URL_PUBLICA, URL_SCRIPTS, fichero)}
        cuerpo['token'] = firmar_jwt(dict(cuerpo))
        respuesta = requests.post(
            url_interna_ds().rstrip('/') + '/docbuilder', json=cuerpo, timeout=(3, 900),
            headers={'Authorization': 'Bearer ' + firmar_jwt({'payload': cuerpo})})
        try:
            urls = list((respuesta.json() or {}).get('urls', {}).values())
        except ValueError:
            urls = []
        if not urls:
            print('  el docbuilder respondió:', respuesta.status_code, repr(respuesta.text[:500]))
            return 1
        salida = requests.get(_reescribir_url_interna(urls[0]), timeout=(3, 300)).content
        destino = '/tmp/provincias-columnas.xlsx'
        open(destino, 'wb').write(salida)
        print('  resultado en', destino, '(%.0f KB)' % (len(salida) / 1024))
        if aplicar:
            import sala_editor
            from api_onlyoffice import _base_documento, invalidar_cache
            dentro = sala_editor.usuarios_conectados(_base_documento(usuario, ruta))
            if dentro is None or dentro:
                print('  NO se aplica: el Excel está abierto en el editor (%s)' % dentro)
                return 2
            carpeta, _, nombre_archivo = ruta.rpartition('/')
            nucleo.subir(usuario, carpeta or '/', nombre_archivo, io.BytesIO(salida))
            invalidar_cache(usuario, ruta)
            print('  aplicado al Drive (la versión anterior queda en el historial)')
    finally:
        os.remove(camino)
    return 0


if __name__ == '__main__':
    # `--solo NOMBRE,NOMBRE` limita el trabajo a esas pestañas (para probar o
    # reintentar una suelta sin rehacer las diez).
    argumentos = sys.argv[3:]
    solo = None
    if '--solo' in argumentos:
        solo = {plano(n) for n in argumentos[argumentos.index('--solo') + 1].split(',')}
    sys.exit(principal(int(sys.argv[1]), sys.argv[2], '--aplicar' in argumentos, solo))
