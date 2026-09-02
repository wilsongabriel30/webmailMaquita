# -*- coding: utf-8 -*-
"""¿Cada acción respeta el permiso? Se pregunta a los endpoints DE VERDAD.

Las rutas usadas no existen a propósito: si el permiso hace su trabajo, la
respuesta es 403 y no se toca el disco. Un 404 o un 200 delata que la acción
llegó más lejos de lo que debía.
"""
import sys
sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')

from flask import Flask

from api_archivos import bp_archivos
from api_crear import bp_crear
from api_extras import bp_extras
from api_drawio import bp_drawio
from api_versiones import bp_versiones
from api_oo_drive import bp_oo_drive
from api_actividad import bp_actividad

app = Flask(__name__)
for bp in (bp_archivos, bp_crear, bp_extras, bp_drawio, bp_versiones,
           bp_oo_drive, bp_actividad):
    app.register_blueprint(bp, url_prefix='/api/almacen')
cliente = app.test_client()

GUAYAS = '/unidades/9/3 Guayas-El Oro Procesos Formativos y Sociales'
ESMER = '/unidades/9/1 Esmeraldas Procesos Formativos y Sociales'

QUIENES = {999: 'ajeno a la unidad',
           44: 'viewer de toda la unidad',
           19: 'editor SOLO en Guayas',
           14: 'manager de la unidad'}


def pedir(quien, metodo, ruta, cuerpo=None, consulta=''):
    cabeceras = {'X-Almacen-Usuario-Id': str(quien)}
    url = '/api/almacen' + ruta + consulta
    if metodo == 'POST':
        r = cliente.post(url, json=cuerpo or {}, headers=cabeceras)
    else:
        r = cliente.get(url, headers=cabeceras)
    return r.status_code


CASOS = [
    # (acción, método, ruta, cuerpo, dónde actúa)
    ('crear documento', 'POST', '/archivos/crear',
     lambda d: {'ruta': d + '/_prueba_permisos.docx', 'tipo': 'docx'}, None),
    ('eliminar',        'POST', '/archivos/eliminar',
     lambda d: {'ruta': d + '/_no_existe.txt'}, None),
    ('renombrar',       'POST', '/archivos/renombrar',
     lambda d: {'ruta': d + '/_no_existe.txt', 'nuevo_nombre': 'otro.txt'}, None),
    ('copiar (destino)', 'POST', '/archivos/copiar',
     lambda d: {'origen': ESMER + '/_no_existe.txt', 'destino': d}, None),
    ('mover (destino)',  'POST', '/archivos/mover',
     lambda d: {'origen': ESMER + '/_no_existe.txt', 'destino': d}, None),
    ('guardar diagrama', 'POST', '/drawio/guardar',
     lambda d: {'xml': '<mxfile/>'}, 'ruta'),
    ('restaurar version', 'POST', '/onlyoffice/restaurar',
     lambda d: {'version_id': 1}, 'ruta'),
    ('comentar',         'POST', '/archivos/comentarios',
     lambda d: {'ruta': d, 'texto': 'prueba de permisos'}, None),
    ('color de carpeta', 'POST', '/carpetas/estilo',
     lambda d: {'folder_id': 'x', 'color': '#ff0000'}, None),
]

print('Cada celda: el codigo que devuelve el endpoint. 403 = bien rechazado.')
print()
for etiqueta, carpeta in (('EN GUAYAS', GUAYAS), ('EN ESMERALDAS', ESMER)):
    print('══', etiqueta)
    print('   %-20s %-20s %-24s %-22s %s' % ('accion', QUIENES[999], QUIENES[44], QUIENES[19], QUIENES[14]))
    for accion, metodo, ruta, cuerpo, en_consulta in CASOS:
        fila = []
        for quien in (999, 44, 19, 14):
            datos = cuerpo(carpeta)
            consulta = ''
            if en_consulta == 'ruta':
                from urllib.parse import quote
                consulta = '?ruta=' + quote(carpeta + '/_prueba_permisos.drawio')
            try:
                codigo = pedir(quien, metodo, ruta, datos, consulta)
            except Exception as excepcion:
                codigo = 'ERR:' + type(excepcion).__name__
            fila.append(codigo)
        print('   %-20s %-20s %-24s %-22s %s' % (accion, fila[0], fila[1], fila[2], fila[3]))
    print()
