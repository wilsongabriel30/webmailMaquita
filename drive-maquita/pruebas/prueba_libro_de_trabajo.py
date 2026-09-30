# -*- coding: utf-8 -*-
"""Prueba del flujo REAL de trabajo con la hoja de respuestas del Drive.

Reproduce lo que hace la gente y comprueba que el motor no se lo estropea:

  1. exporta las respuestas de un formulario a un libro del Drive;
  2. sobre ese libro, la persona añade **su propia pestaña** con fórmulas que
     extraen de la hoja de respuestas (el patrón de las provincias), una
     **columna calculada** dentro de la propia tabla y **formato**;
  3. a partir de ahí se edita el formulario y las respuestas de todas las
     maneras posibles, y después de cada cambio se comprueba que la pestaña
     propia, sus fórmulas, la columna calculada y el formato **siguen vivos** y
     dando el valor correcto.

Es la prueba de que «yo puedo editar, poner hojas y cambiar formato y eso no
debe afectar a la actualización de las respuestas», para cualquier libro.

Uso:  python prueba_libro_de_trabajo.py <usuario> [--dejar]

Autoría: Equipo de Tecnología Maquita — 2026-09-22
"""
import io
import json
import os
import sys
import uuid
from datetime import datetime

sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')

import openpyxl

import encuestas_bd as ebd
import encuestas_hoja as hoja_mod
import encuestas_hoja_libro as libro
import nucleo_archivos as nucleo

CARPETA = '/PRUEBAS FLUJO'
NOMBRE = 'Libro de trabajo %s' % datetime.now().strftime('%H%M%S')
PESTANA = 'RESUMEN'
fallos = []


def comprobar(paso, condicion, detalle=''):
    print('  %-56s %s' % (paso, 'BIEN' if condicion else 'MAL  <-- %s' % detalle))
    if not condicion:
        fallos.append(paso)


def pregunta(titulo):
    return {'clase': 'pregunta', 'id': str(uuid.uuid4()), 'tipo': 'texto_corto',
            'titulo': titulo, 'obligatoria': False, 'opciones': []}


def guardar_forma(usuario, ruta, definicion):
    carpeta, _, nombre = ruta.rpartition('/')
    nucleo.subir(usuario, carpeta or '/', nombre,
                 io.BytesIO(json.dumps(definicion, ensure_ascii=False).encode('utf-8')))


def exportar(usuario, encuesta_id, definicion, ruta_hoja):
    fila = ebd.obtener(encuesta_id)
    contenido, estado = libro.preparar(fila, definicion, usuario, ruta_hoja)
    if contenido is not None:
        carpeta, _, nombre = ruta_hoja.rpartition('/')
        nucleo.subir(usuario, carpeta or '/', nombre, contenido)
    if estado is not None:
        libro.confirmar(definicion['id'], estado)


def montar_trabajo_de_la_persona(usuario, ruta_hoja):
    """Lo que hace la persona sobre el libro: una pestaña propia con fórmulas
    que extraen de la hoja de respuestas, una columna calculada en la tabla y
    formato de color."""
    fisica = nucleo.ruta_fisica(usuario, ruta_hoja)
    wb = openpyxl.load_workbook(fisica)
    respuestas = wb[wb.sheetnames[0]]
    hoja = wb.create_sheet(PESTANA)
    hoja['A1'] = 'Resumen propio'
    hoja['A2'] = '=COUNTA(\'%s\'!C5:C500)' % respuestas.title
    for i in range(3, 13):
        hoja.cell(row=i, column=1).value = "='%s'!C%d" % (respuestas.title, i + 2)
        hoja.cell(row=i, column=2).value = "='%s'!D%d" % (respuestas.title, i + 2)
    # Columna propia DENTRO de la tabla de respuestas y un formato a mano.
    ultima = max(c for c in range(1, 60) if respuestas.cell(row=4, column=c).value)
    respuestas.cell(row=4, column=ultima + 1).value = 'MI COLUMNA'
    for f in range(5, 15):
        respuestas.cell(row=f, column=ultima + 1).value = '=LEN(C%d)' % f
    respuestas.cell(row=4, column=1).font = openpyxl.styles.Font(bold=True, color='FF0000')
    memoria = io.BytesIO()
    wb.save(memoria)
    memoria.seek(0)
    carpeta, _, nombre = ruta_hoja.rpartition('/')
    nucleo.subir(usuario, carpeta or '/', nombre, memoria)


def estado_libro(usuario, ruta_hoja):
    fisica = nucleo.ruta_fisica(usuario, ruta_hoja)
    wb = openpyxl.load_workbook(fisica)
    respuestas = wb[wb.sheetnames[0]]
    resumen = wb[PESTANA] if PESTANA in wb.sheetnames else None
    encabezados = [str(respuestas.cell(row=4, column=c).value or '')
                   for c in range(1, 60) if respuestas.cell(row=4, column=c).value]
    mi_columna = None
    for c in range(1, 60):
        if str(respuestas.cell(row=4, column=c).value or '') == 'MI COLUMNA':
            mi_columna = c
    formulas_mias = 0
    if mi_columna:
        formulas_mias = sum(1 for f in range(5, 15)
                            if str(respuestas.cell(row=f, column=mi_columna).value or '')
                            .startswith('='))
    return {
        'hojas': wb.sheetnames,
        'resumen_formulas': sum(1 for i in range(2, 13)
                                if resumen and str(resumen.cell(row=i, column=1).value or '')
                                .startswith('=')) if resumen else 0,
        'encabezados': encabezados,
        'mi_columna': mi_columna,
        'formulas_mias': formulas_mias,
        'negrita': bool(respuestas.cell(row=4, column=1).font
                        and respuestas.cell(row=4, column=1).font.bold),
        'filas': sum(1 for f in range(5, 200) if respuestas.cell(row=f, column=1).value
                     not in (None, '')),
    }


def principal(usuario, dejar):
    ruta_forma = '%s/%s.forma' % (CARPETA, NOMBRE)
    ruta_hoja = '%s/%s (respuestas).xlsx' % (CARPETA, NOMBRE)
    try:
        nucleo.crear_carpeta(usuario, '/', CARPETA.strip('/'))
    except Exception:
        pass

    a, b = pregunta('Nombre'), pregunta('Cantón')
    definicion = {'id': str(uuid.uuid4()), 'titulo': NOMBRE, 'elementos': [a, b]}
    guardar_forma(usuario, ruta_forma, definicion)
    ebd.registrar(definicion['id'], usuario, ruta_forma, NOMBRE)
    hoja_mod.vincular(definicion['id'], ruta_hoja)

    ebd.guardar_respuesta(definicion['id'], json.dumps({a['id']: 'Ana', b['id']: 'Guaranda'}), usuario)
    exportar(usuario, definicion['id'], definicion, ruta_hoja)
    montar_trabajo_de_la_persona(usuario, ruta_hoja)
    inicial = estado_libro(usuario, ruta_hoja)
    print('\n  La persona ha montado su libro: %s, %d fórmulas propias en «%s», '
          'columna «MI COLUMNA» con %d fórmulas'
          % (inicial['hojas'], inicial['resumen_formulas'], PESTANA, inicial['formulas_mias']))

    def revisar(paso):
        hoy = estado_libro(usuario, ruta_hoja)
        comprobar('%s: la pestaña propia sigue' % paso, PESTANA in hoy['hojas'], hoy['hojas'])
        comprobar('%s: sus fórmulas siguen' % paso,
                  hoy['resumen_formulas'] == inicial['resumen_formulas'],
                  '%d de %d' % (hoy['resumen_formulas'], inicial['resumen_formulas']))
        comprobar('%s: la columna calculada sigue' % paso,
                  hoy['mi_columna'] is not None and hoy['formulas_mias'] >= 10,
                  'columna %s con %d fórmulas' % (hoy['mi_columna'], hoy['formulas_mias']))
        comprobar('%s: el formato sigue' % paso, hoy['negrita'], 'sin negrita')
        return hoy

    ebd.guardar_respuesta(definicion['id'], json.dumps({a['id']: 'Luis', b['id']: 'Chillanes'}), usuario)
    exportar(usuario, definicion['id'], definicion, ruta_hoja)
    hoy = revisar('respuesta nueva')
    comprobar('respuesta nueva: llega a la hoja', hoy['filas'] == 2, '%d filas' % hoy['filas'])

    c = pregunta('Teléfono')
    definicion['elementos'].append(c)
    guardar_forma(usuario, ruta_forma, definicion)
    exportar(usuario, definicion['id'], definicion, ruta_hoja)
    hoy = revisar('pregunta nueva')
    comprobar('pregunta nueva: su columna se añade',
              'Teléfono' in hoy['encabezados'], hoy['encabezados'])
    comprobar('pregunta nueva: NO pisa la columna de la persona',
              hoy['encabezados'].index('MI COLUMNA') < hoy['encabezados'].index('Teléfono')
              if 'Teléfono' in hoy['encabezados'] else False, hoy['encabezados'])

    b['titulo'] = 'Cantón o parroquia'
    guardar_forma(usuario, ruta_forma, definicion)
    exportar(usuario, definicion['id'], definicion, ruta_hoja)
    revisar('pregunta renombrada')

    respuestas = ebd.listar_respuestas(definicion['id'])
    ebd.actualizar_respuesta(respuestas[0]['id'], json.dumps(
        {a['id']: 'Luis Alberto', b['id']: 'Chillanes', c['id']: '099'}))
    exportar(usuario, definicion['id'], definicion, ruta_hoja)
    revisar('respuesta modificada')

    ebd.borrar_respuesta(definicion['id'], respuestas[-1]['id'])
    exportar(usuario, definicion['id'], definicion, ruta_hoja)
    hoy = revisar('respuesta borrada')
    comprobar('respuesta borrada: queda una fila', hoy['filas'] == 1, '%d filas' % hoy['filas'])

    print('\nRESULTADO: %s' % ('el libro de trabajo aguanta todo el flujo' if not fallos
                               else '%d comprobaciones fallan' % len(fallos)))
    if not dejar:
        for ruta in (ruta_forma, ruta_hoja):
            try:
                nucleo.enviar_a_papelera(usuario, ruta)
            except Exception:
                pass
        ebd.borrar_respuestas(definicion['id'])
        ebd.bd.ejecutar('DELETE FROM encuestas WHERE id = %s', (definicion['id'],))
        ebd.bd.ejecutar('DELETE FROM encuesta_hoja_estado WHERE encuesta_id = %s',
                        (definicion['id'],))
        print('  pruebas retiradas')
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(principal(int(sys.argv[1]), '--dejar' in sys.argv))
