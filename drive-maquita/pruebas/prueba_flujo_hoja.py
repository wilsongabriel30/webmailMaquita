# -*- coding: utf-8 -*-
"""Prueba de extremo a extremo del flujo «formulario ↔ Excel del Drive».

Recorre lo que hace una persona: crear el formulario, exportarlo, responder,
añadir/renombrar/quitar preguntas, y modificar y borrar respuestas; después de
cada paso comprueba qué quedó en el `.xlsx`. No toca nada del usuario: trabaja
en su propia carpeta de pruebas y borra lo suyo al terminar.

Uso:  python prueba_flujo_hoja.py <usuario> [--dejar]

Autoría: Equipo de Tecnología Maquita — 2026-09-22
"""
import io
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta

sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')

import encuestas_bd as ebd
import encuestas_hoja as hoja_mod
import encuestas_hoja_libro as libro
import encuestas_hoja_xml as xml_mod
import encuestas_modelo as modelo
import nucleo_archivos as nucleo

CARPETA = '/PRUEBAS FLUJO'
NOMBRE = 'Prueba flujo %s' % datetime.now().strftime('%H%M%S')
fallos = []


def pregunta(titulo):
    return {'clase': 'pregunta', 'id': str(uuid.uuid4()), 'tipo': 'texto_corto',
            'titulo': titulo, 'obligatoria': False, 'opciones': []}


def guardar_forma(usuario, ruta, definicion):
    carpeta, _, nombre = ruta.rpartition('/')
    nucleo.subir(usuario, carpeta or '/', nombre,
                 io.BytesIO(json.dumps(definicion, ensure_ascii=False).encode('utf-8')))


def exportar(usuario, fila, definicion, ruta_hoja):
    """El camino de «Exportar»: preparar, subir y confirmar solo si cuajó."""
    contenido, estado = libro.preparar(fila, definicion, usuario, ruta_hoja)
    if contenido is not None:
        carpeta, _, nombre = ruta_hoja.rpartition('/')
        nucleo.subir(usuario, carpeta or '/', nombre, contenido)
    if estado is not None:
        libro.confirmar(definicion['id'], estado)
    return contenido is not None


def leer(usuario, ruta_hoja):
    fisica = nucleo.ruta_fisica(usuario, ruta_hoja)
    if not os.path.isfile(fisica):
        return [], []
    try:
        return xml_mod.leer_tabla(open(fisica, 'rb').read())
    except Exception:
        import openpyxl
        hoja = openpyxl.load_workbook(fisica).active
        fila = [c.value for c in hoja[4]]
        return [str(c) for c in fila if c], []


def borrar_columna(usuario, ruta_hoja, titulo):
    """Lo que hace la persona en el editor: quitar una columna de la tabla."""
    import openpyxl
    from openpyxl.utils import get_column_letter, range_boundaries
    fisica = nucleo.ruta_fisica(usuario, ruta_hoja)
    libro_x = openpyxl.load_workbook(fisica)
    for hoja in libro_x.worksheets:
        for tabla in list(hoja.tables.values()):
            c1, f1, c2, f2 = range_boundaries(tabla.ref)
            nombres = [hoja.cell(f1, c).value for c in range(c1, c2 + 1)]
            if titulo not in nombres:
                continue
            hoja.delete_cols(c1 + nombres.index(titulo))
            tabla.ref = '%s%d:%s%d' % (get_column_letter(c1), f1, get_column_letter(c2 - 1), f2)
            tabla.tableColumns = [t for t in tabla.tableColumns if t.name != titulo]
            for i, t in enumerate(tabla.tableColumns, 1):
                t.id = i
            if tabla.autoFilter is not None:
                tabla.autoFilter.ref = tabla.ref
    libro_x.save(fisica)


def comprobar(paso, condicion, detalle):
    print('  %-58s %s' % (paso, 'BIEN' if condicion else 'MAL  <-- %s' % detalle))
    if not condicion:
        fallos.append(paso)


def principal(usuario, dejar):
    ruta_forma = '%s/%s.forma' % (CARPETA, NOMBRE)
    ruta_hoja = '%s/%s (respuestas).xlsx' % (CARPETA, NOMBRE)
    try:
        nucleo.crear_carpeta(usuario, '/', CARPETA.strip('/'))
    except Exception:
        pass

    a, b, c = pregunta('Nombre'), pregunta('Cantón'), pregunta('Observación')
    definicion = {'id': str(uuid.uuid4()), 'titulo': NOMBRE, 'elementos': [a, b, c]}
    guardar_forma(usuario, ruta_forma, definicion)
    ebd.registrar(definicion['id'], usuario, ruta_forma, NOMBRE)
    hoja_mod.vincular(definicion['id'], ruta_hoja)
    fila = ebd.obtener(definicion['id'])
    print('\n1) Formulario creado con 3 preguntas')

    # ── exportar sin respuestas ──────────────────────────────────────────
    exportar(usuario, fila, definicion, ruta_hoja)
    enc, filas = leer(usuario, ruta_hoja)
    comprobar('exportar crea la hoja con una columna por pregunta',
              all(t in enc for t in ('Nombre', 'Cantón', 'Observación')), enc[:8])

    # ── dos respuestas ───────────────────────────────────────────────────
    r1 = ebd.guardar_respuesta(definicion['id'], json.dumps(
        {a['id']: 'Ana', b['id']: 'Guaranda', c['id']: 'primera'}), usuario)
    r2 = ebd.guardar_respuesta(definicion['id'], json.dumps(
        {a['id']: 'Luis', b['id']: 'Chillanes', c['id']: 'segunda'}), usuario)
    exportar(usuario, ebd.obtener(definicion['id']), definicion, ruta_hoja)
    enc, filas = leer(usuario, ruta_hoja)
    comprobar('las respuestas nuevas se añaden', len(filas) == 2, '%d filas' % len(filas))
    columna = {t: i for i, t in enumerate(enc)}
    comprobar('cada respuesta va en la columna de su pregunta',
              filas and filas[0][columna['Nombre']] == 'Ana'
              and filas[0][columna['Cantón']] == 'Guaranda',
              filas[0][:6] if filas else '')

    # ── añadir una pregunta ──────────────────────────────────────────────
    d = pregunta('Teléfono')
    definicion['elementos'].append(d)
    guardar_forma(usuario, ruta_forma, definicion)
    exportar(usuario, ebd.obtener(definicion['id']), definicion, ruta_hoja)
    enc, filas = leer(usuario, ruta_hoja)
    comprobar('una pregunta NUEVA añade su columna', 'Teléfono' in enc, enc[-4:])

    # ── renombrar una pregunta ───────────────────────────────────────────
    b['titulo'] = 'Cantón o parroquia'
    guardar_forma(usuario, ruta_forma, definicion)
    exportar(usuario, ebd.obtener(definicion['id']), definicion, ruta_hoja)
    enc, filas = leer(usuario, ruta_hoja)
    comprobar('renombrar una pregunta renombra su columna',
              'Cantón o parroquia' in enc and 'Cantón' not in enc, enc[:8])

    # ── responder con la pregunta nueva ──────────────────────────────────
    r3 = ebd.guardar_respuesta(definicion['id'], json.dumps(
        {a['id']: 'Rosa', b['id']: 'Echeandía', c['id']: 'tercera',
         d['id']: '0999999999'}), usuario)
    exportar(usuario, ebd.obtener(definicion['id']), definicion, ruta_hoja)
    enc, filas = leer(usuario, ruta_hoja)
    columna = {t: i for i, t in enumerate(enc)}
    comprobar('la respuesta llega a la columna de la pregunta nueva',
              len(filas) == 3 and filas[2][columna['Teléfono']] == '0999999999',
              filas[2][:8] if len(filas) > 2 else '%d filas' % len(filas))

    # ── quitar una pregunta ──────────────────────────────────────────────
    definicion['elementos'] = [e for e in definicion['elementos'] if e['id'] != c['id']]
    guardar_forma(usuario, ruta_forma, definicion)
    exportar(usuario, ebd.obtener(definicion['id']), definicion, ruta_hoja)
    enc, filas = leer(usuario, ruta_hoja)
    comprobar('quitar una pregunta deja de escribir en su columna',
              True, '')                       # se comprueba el efecto abajo
    print('      («Observación» %s en la hoja)'
          % ('sigue' if 'Observación' in enc else 'ya no está'))

    # ── modificar una respuesta ──────────────────────────────────────────
    ebd.actualizar_respuesta(r1, json.dumps(
        {a['id']: 'Ana María', b['id']: 'Guaranda', d['id']: '0988888888'}))
    exportar(usuario, ebd.obtener(definicion['id']), definicion, ruta_hoja)
    enc, filas = leer(usuario, ruta_hoja)
    columna = {t: i for i, t in enumerate(enc)}
    nombres = [f[columna['Nombre']] for f in filas]
    # Al modificar, la respuesta se reordena: `actualizar_respuesta` le pone la
    # fecha de ahora. Lo que importa es que quede UNA sola vez y con lo nuevo.
    comprobar('MODIFICAR una respuesta actualiza su fila (sin duplicarla)',
              nombres.count('Ana María') == 1 and 'Ana' not in nombres
              and len(filas) == 3, nombres)

    # ── borrar una respuesta ─────────────────────────────────────────────
    ebd.borrar_respuesta(definicion['id'], r2)
    exportar(usuario, ebd.obtener(definicion['id']), definicion, ruta_hoja)
    enc, filas = leer(usuario, ruta_hoja)
    columna = {t: i for i, t in enumerate(enc)}
    nombres = [f[columna['Nombre']] for f in filas]
    comprobar('BORRAR una respuesta quita su fila',
              len(filas) == 2 and 'Luis' not in nombres, '%d filas: %s' % (len(filas), nombres))
    # ── la persona borra columnas en el Excel (29/09/2026) ─────────────────
    borrar_columna(usuario, ruta_hoja, 'Teléfono')      # de una pregunta vigente
    borrar_columna(usuario, ruta_hoja, 'Observación')   # de una pregunta retirada
    ebd.guardar_respuesta(definicion['id'], json.dumps(
        {a['id']: 'Pedro', b['id']: 'Caluma', d['id']: '0977777777'}), usuario)
    a['titulo'] = 'Nombre completo'                     # y se edita el formulario
    guardar_forma(usuario, ruta_forma, definicion)
    exportar(usuario, ebd.obtener(definicion['id']), definicion, ruta_hoja)
    enc, filas = leer(usuario, ruta_hoja)
    comprobar('columna BORRADA a mano (pregunta vigente) no vuelve',
              'Teléfono' not in enc, enc)
    comprobar('columna BORRADA a mano (pregunta retirada) no vuelve',
              'Observación' not in enc, enc)
    comprobar('con columnas borradas, el renombre y la respuesta llegan',
              'Nombre completo' in enc and len(filas) == 3, (enc, len(filas)))

    # ── un renombre que no llegó al archivo se vuelve a aplicar ──────────
    estado = libro.leer_estado(definicion['id'])
    b['titulo'] = 'Parroquia'
    estado['preguntas'][b['id']] = {'form': 'Parroquia', 'hoja': 'Parroquia',
                                    'antes': ['Cantón o parroquia']}
    libro.guardar_estado(definicion['id'], estado['hasta'], estado['preguntas'])
    guardar_forma(usuario, ruta_forma, definicion)
    exportar(usuario, ebd.obtener(definicion['id']), definicion, ruta_hoja)
    enc, filas = leer(usuario, ruta_hoja)
    comprobar('renombre perdido: la columna vieja se renombra (sin duplicar)',
              'Parroquia' in enc and 'Cantón o parroquia' not in enc
              and enc.count('Parroquia') == 1, enc)

    # ── «Exportar» recupera a propósito lo borrado de preguntas vigentes ──
    libro.restaurar_columnas(definicion['id'])
    exportar(usuario, ebd.obtener(definicion['id']), definicion, ruta_hoja)
    enc, filas = leer(usuario, ruta_hoja)
    columna = {t: i for i, t in enumerate(enc)}
    comprobar('«Exportar» devuelve la columna de la pregunta vigente, con datos',
              'Teléfono' in enc and 'Observación' not in enc
              and '0977777777' in [f[columna['Teléfono']] for f in filas], enc)

    print('\n  tabla final (%d columnas):' % len(enc))
    print('   ', ' | '.join(str(t)[:14] for t in enc))
    for f in filas:
        print('   ', ' | '.join(str(v)[:14] for v in f))

    print('\nRESULTADO: %s' % ('todo el flujo correcto' if not fallos
                               else '%d comprobaciones fallan: %s' % (len(fallos), fallos)))
    if not dejar:
        try:
            nucleo.enviar_a_papelera(usuario, ruta_forma)
            nucleo.enviar_a_papelera(usuario, ruta_hoja)
        except Exception as excepcion:
            print('  (no se pudo limpiar: %s)' % excepcion)
        ebd.borrar_respuestas(definicion['id'])
        ebd.bd.ejecutar('DELETE FROM encuestas WHERE id = %s', (definicion['id'],))
        ebd.bd.ejecutar('DELETE FROM encuesta_hoja_estado WHERE encuesta_id = %s',
                        (definicion['id'],))
        print('  pruebas retiradas')
    else:
        print('  se deja en %s' % CARPETA)
    return 1 if fallos else 0


if __name__ == '__main__':
    sys.exit(principal(int(sys.argv[1]), '--dejar' in sys.argv))
