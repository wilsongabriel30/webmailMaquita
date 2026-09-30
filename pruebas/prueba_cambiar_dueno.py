# -*- coding: utf-8 -*-
"""Prueba de «cambiar de dueño» un formulario, de extremo a extremo.

Monta un formulario publicado, con respuestas, hoja de respuestas y un adjunto,
en el Drive de la cuenta de pruebas; lo pasa a un espacio TEMPORAL (un número
de usuario que no es de nadie) y comprueba que sigue siendo el mismo
formulario. Borra todo lo suyo al terminar.

Uso:  python prueba_cambiar_dueno.py <usuario de pruebas>

Autoría: Equipo de Tecnología Maquita — 2026-09-29
"""
import io
import json
import os
import shutil
import sys
import uuid
from datetime import datetime

sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')

import almacen_bd as bd
import encuestas_archivos as archivos_mod
import encuestas_bd as ebd
import encuestas_hoja as hoja_mod
import encuestas_hoja_libro as libro
import encuestas_hoja_xml as xml_mod
import formularios_cambiar_dueno as cambio
import nucleo_archivos as nucleo
from seguridad_rutas import raiz_datos, ruta_fisica

TEMPORAL = 990054
CARPETA = '/PRUEBAS DUEÑO'
fallos = []


def comprobar(paso, condicion, detalle=''):
    print('  %-64s %s' % (paso, 'BIEN' if condicion else 'MAL  <-- %s' % (detalle,)))
    if not condicion:
        fallos.append(paso)


def exportar(usuario, definicion, ruta_hoja):
    contenido, estado = libro.preparar(ebd.obtener(definicion['id']), definicion,
                                       usuario, ruta_hoja)
    if contenido is not None:
        nucleo.subir(usuario, ruta_hoja.rsplit('/', 1)[0], ruta_hoja.rsplit('/', 1)[-1], contenido)
    if estado is not None:
        libro.confirmar(definicion['id'], estado)


def montar(usuario, nombre):
    """Formulario publicado con dos respuestas, hoja y un adjunto."""
    ruta = '%s/%s.forma' % (CARPETA, nombre)
    hoja = '%s/%s (respuestas).xlsx' % (CARPETA, nombre)
    a = {'clase': 'pregunta', 'id': str(uuid.uuid4()), 'tipo': 'texto_corto',
         'titulo': 'Nombre', 'obligatoria': False, 'opciones': []}
    b = dict(a, id=str(uuid.uuid4()), tipo='archivo', titulo='Documento')
    definicion = {'id': str(uuid.uuid4()), 'titulo': nombre, 'elementos': [a, b]}
    try:
        nucleo.crear_carpeta(usuario, '/', CARPETA.strip('/'))
    except Exception:
        pass
    nucleo.subir(usuario, CARPETA, nombre + '.forma',
                 io.BytesIO(json.dumps(definicion, ensure_ascii=False).encode('utf-8')))
    ebd.registrar(definicion['id'], usuario, ruta, nombre)
    ebd.publicar(definicion['id'])
    adjuntos = archivos_mod.carpeta_destino(ruta)
    nucleo.crear_carpeta(usuario, CARPETA, adjuntos.rsplit('/', 1)[-1])
    nucleo.subir(usuario, adjuntos, 'cedula.pdf', io.BytesIO(b'%PDF-1.4 prueba'))
    ficha = {'id': uuid.uuid4().hex, 'nombre': 'cedula.pdf', 'ruta': adjuntos + '/cedula.pdf'}
    ebd.guardar_respuesta(definicion['id'], json.dumps({a['id']: 'Ana', b['id']: [ficha]}), None)
    ebd.guardar_respuesta(definicion['id'], json.dumps({a['id']: 'Luis'}), None)
    hoja_mod.vincular(definicion['id'], hoja)
    exportar(usuario, definicion, hoja)
    return ruta, hoja, adjuntos, definicion, a


def revisar(etiqueta, usuario, montado, carpeta_nueva):
    ruta, hoja, adjuntos, definicion, pregunta = montado
    antes = ebd.obtener(definicion['id'])
    plan = cambio.planear(usuario, ruta, TEMPORAL, carpeta_nueva)
    comprobar('%s: el plan no encuentra impedimentos' % etiqueta, not plan['bloqueos'],
              plan['bloqueos'])
    comprobar('%s: se lleva formulario, hoja y adjuntos' % etiqueta,
              [p['que'] for p in plan['piezas']]
              == ['formulario', 'hoja de respuestas', 'carpeta de adjuntos'], plan['piezas'])
    comprobar('%s: planear no cambia nada' % etiqueta,
              ebd.obtener(definicion['id']) == antes and os.path.isfile(ruta_fisica(usuario, ruta)))
    cambio.aplicar(plan, espera=0)

    destino = carpeta_nueva or CARPETA
    nueva = destino + '/' + ruta.rsplit('/', 1)[-1]
    hoja_nueva = destino + '/' + hoja.rsplit('/', 1)[-1]
    despues = ebd.obtener(definicion['id'])
    comprobar('%s: el registro pasa al nuevo dueño' % etiqueta,
              int(despues['propietario']) == TEMPORAL and despues['ruta'] == nueva
              and despues['hoja_ruta'] == hoja_nueva,
              (despues['propietario'], despues['ruta'], despues['hoja_ruta']))
    comprobar('%s: conserva el enlace público y el código' % etiqueta,
              despues['token'] == antes['token'] and despues['codigo'] == antes['codigo']
              and bool(antes['token']))
    comprobar('%s: conserva las respuestas' % etiqueta,
              ebd.contar_respuestas(definicion['id']) == 2)
    comprobar('%s: los archivos están en el Drive del nuevo dueño' % etiqueta,
              all(os.path.exists(ruta_fisica(TEMPORAL, p['a'])) for p in plan['piezas'])
              and os.path.isfile(ruta_fisica(TEMPORAL, plan['adjuntos'][1] + '/cedula.pdf')))
    comprobar('%s: ya no están en el Drive del anterior' % etiqueta,
              not any(os.path.exists(ruta_fisica(usuario, p['de'])) for p in plan['piezas']))
    en_papelera = [f['ruta_original'] for f in bd.consultar(
        'SELECT ruta_original FROM papelera WHERE usuario_id = %s', (usuario,))]
    comprobar('%s: los originales quedan en su papelera' % etiqueta,
              all(p['de'] in en_papelera for p in plan['piezas']), en_papelera[-4:])

    # Lo que pasa cuando el nuevo dueño lo abre: el formulario se registra otra vez.
    from api_encuestas import leer_definicion
    leida = leer_definicion(TEMPORAL, nueva)
    fila = ebd.registrar(leida['id'], TEMPORAL, nueva, 'x')
    comprobar('%s: al abrirlo el nuevo dueño sigue siendo el mismo' % etiqueta,
              fila is not None and fila['id'] == definicion['id'], fila and fila['id'])
    rutas = [f.get('ruta') for r in ebd.listar_respuestas(definicion['id'])
             for v in (r['datos'] or {}).values() if isinstance(v, list) for f in v]
    comprobar('%s: el adjunto de la respuesta apunta a donde está ahora' % etiqueta,
              rutas == [plan['adjuntos'][1] + '/cedula.pdf']
              and os.path.isfile(ruta_fisica(TEMPORAL, rutas[0])), rutas)
    ebd.guardar_respuesta(definicion['id'], json.dumps({pregunta['id']: 'Rosa'}), None)
    exportar(TEMPORAL, leida, hoja_nueva)
    encabezados, filas = xml_mod.leer_tabla(open(ruta_fisica(TEMPORAL, hoja_nueva), 'rb').read())
    nombres = [f[encabezados.index('Nombre')] for f in filas] if 'Nombre' in encabezados else []
    comprobar('%s: una respuesta nueva llega a la hoja del nuevo dueño' % etiqueta,
              nombres == ['Ana', 'Luis', 'Rosa'], nombres)
    return definicion['id']


def limpiar(usuario, ids):
    for encuesta_id in ids:
        ebd.borrar_respuestas(encuesta_id)
        for tabla in ('encuesta_hoja_estado', 'encuesta_respuestas_borradas'):
            try:
                bd.ejecutar('DELETE FROM %s WHERE encuesta_id = %%s' % tabla, (encuesta_id,))
            except Exception:
                pass
        bd.ejecutar('DELETE FROM encuestas WHERE id = %s', (encuesta_id,))
    for fila in bd.consultar('SELECT nombre_fisico FROM papelera WHERE usuario_id = %s '
                             'AND ruta_original LIKE %s', (usuario, CARPETA + '/%')):
        nucleo.eliminar_de_papelera(usuario, fila['nombre_fisico'])
    try:
        nucleo.enviar_a_papelera(usuario, CARPETA)
        for fila in bd.consultar('SELECT nombre_fisico FROM papelera WHERE usuario_id = %s '
                                 'AND ruta_original = %s', (usuario, CARPETA)):
            nucleo.eliminar_de_papelera(usuario, fila['nombre_fisico'])
    except Exception:
        pass
    for tabla, columna in (('indice_nombres', 'usuario_id'), ('indice_contenido', 'usuario_id'),
                           ('versiones', 'usuario_id'), ('cuotas_uso', 'usuario_id'),
                           ('papelera', 'usuario_id'), ('actividad', 'usuario_id'),
                           ('indice_estado', 'usuario_id')):
        try:
            bd.ejecutar('DELETE FROM %s WHERE %s = %%s' % (tabla, columna), (TEMPORAL,))
        except Exception:
            pass
    shutil.rmtree(os.path.join(raiz_datos(), str(TEMPORAL)), ignore_errors=True)


def principal(usuario):
    if bd.consultar('SELECT 1 FROM usuarios WHERE id = %s', (TEMPORAL,), nomina=True) \
            or os.path.exists(os.path.join(raiz_datos(), str(TEMPORAL))):
        raise SystemExit('El espacio temporal %s está en uso: no se prueba.' % TEMPORAL)
    marca = datetime.now().strftime('%H%M%S')
    ids = []
    try:
        print('\n1) A la misma carpeta')
        ids.append(revisar('misma carpeta', usuario, montar(usuario, 'Dueño A ' + marca), None))
        print('\n2) A otra carpeta')
        ids.append(revisar('otra carpeta', usuario, montar(usuario, 'Dueño B ' + marca),
                           '/Formularios recibidos'))
        print('\n3) Lo que no se debe poder')
        montado = montar(usuario, 'Dueño C ' + marca)
        ids.append(montado[3]['id'])
        nucleo.crear_carpeta(TEMPORAL, '/', CARPETA.strip('/'))
        nucleo.subir(TEMPORAL, CARPETA, montado[0].rsplit('/', 1)[-1], io.BytesIO(b'{}'))
        plan = cambio.planear(usuario, montado[0], TEMPORAL)
        comprobar('si en destino ya hay un archivo con ese nombre, no se pisa',
                  any('ya existe' in b for b in plan['bloqueos']), plan['bloqueos'])
        comprobar('pasárselo a uno mismo no hace nada',
                  bool(cambio.planear(usuario, montado[0], usuario)['bloqueos']))
        comprobar('una ruta que no es un formulario se rechaza',
                  bool(cambio.planear(usuario, montado[1], TEMPORAL)['bloqueos']))
    finally:
        limpiar(usuario, ids)
    print('\nRESULTADO: %s' % ('cambiar de dueño funciona' if not fallos
                               else '%d comprobaciones fallan: %s' % (len(fallos), fallos)))
    print('  pruebas retiradas')
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(principal(int(sys.argv[1])))
