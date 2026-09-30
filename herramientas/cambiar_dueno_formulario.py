# -*- coding: utf-8 -*-
"""Cambia de dueño un formulario del Drive (con su hoja y sus adjuntos).

Conserva el enlace público, el código QR y las respuestas. Sin `--aplicar`
solo dice lo que haría. Los originales quedan en la papelera del dueño anterior.

Uso:
  python cambiar_dueno_formulario.py <de> "<ruta del .forma>" <a> [--carpeta "/Destino"] [--aplicar]

`<de>` y `<a>` son el número de usuario, el nombre de usuario o el correo.
La ruta es la del Drive del dueño actual, p. ej. "/Encuestas/Clima.forma".

Autoría: Equipo de Tecnología Maquita — 2026-09-29
"""
import sys

sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')

import almacen_bd as bd
import formularios_cambiar_dueno as cambio


def persona(dato):
    """La fila del usuario activo que corresponde a un id, usuario o correo."""
    dato = str(dato).strip()
    if dato.isdigit():
        filas = bd.consultar('SELECT id, username, email, full_name, active FROM usuarios '
                             'WHERE id = %s', (int(dato),), nomina=True)
    else:
        filas = bd.consultar('SELECT id, username, email, full_name, active FROM usuarios '
                             'WHERE lower(username) = lower(%s) OR lower(email) = lower(%s)',
                             (dato, dato), nomina=True)
    if len(filas) != 1:
        raise SystemExit('«%s»: %s' % (dato, 'no existe esa persona' if not filas
                                       else 'hay %d personas con ese dato' % len(filas)))
    if not filas[0]['active']:
        raise SystemExit('«%s»: la cuenta está desactivada' % dato)
    return filas[0]


def principal(argumentos):
    aplicar = '--aplicar' in argumentos
    carpeta = None
    if '--carpeta' in argumentos:
        carpeta = argumentos[argumentos.index('--carpeta') + 1]
        argumentos = [a for a in argumentos if a not in ('--carpeta', carpeta)]
    argumentos = [a for a in argumentos if a != '--aplicar']
    if len(argumentos) != 3:
        raise SystemExit(__doc__)
    de, a = persona(argumentos[0]), persona(argumentos[2])
    plan = cambio.planear(de['id'], argumentos[1], a['id'], carpeta)

    print('Formulario : %s' % plan['ruta'])
    print('De         : %s (%s, usuario %s)' % (de['full_name'] or de['username'],
                                                de['email'], de['id']))
    print('A          : %s (%s, usuario %s)' % (a['full_name'] or a['username'],
                                                a['email'], a['id']))
    print('Respuestas : %s' % plan.get('respuestas', 0))
    if plan['unidad']:
        print('Está en una unidad compartida: los archivos no se mueven, cambia el responsable.')
    for pieza in plan['piezas']:
        print('  · %-20s %s  →  %s' % (pieza['que'], pieza['de'], pieza['a']))
    for aviso in plan['avisos']:
        print('  AVISO: %s' % aviso)
    for bloqueo in plan['bloqueos']:
        print('  NO SE PUEDE: %s' % bloqueo)
    if plan['bloqueos']:
        return 1
    if not aplicar:
        print('\nNo se ha cambiado nada. Para hacerlo, añade --aplicar.')
        return 0
    hecho = cambio.aplicar(plan, a)
    print('\nHECHO. El formulario está en %s del Drive de %s.' % (hecho['ruta'], a['username']))
    print('Los originales quedaron en la papelera de %s.' % de['username'])
    return 0


if __name__ == '__main__':
    sys.exit(principal(sys.argv[1:]))
