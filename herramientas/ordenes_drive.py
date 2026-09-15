#!/usr/bin/env python3
"""Órdenes para la app «Drive Maquita» de Windows (servidor → equipo).

Canal simple y sin puertos nuevos: la orden se deja como un archivo JSON dentro
de `.registro-drive/` del Drive de la persona, que es la carpeta por la que su
app ya pasa cada 5 minutos (sube ahí su ficha y sus registros). La app lee
`ordenes.json`, ejecuta lo que reconoce y deja el resultado en
`ordenes-resultado.json`.

Uso:
    ordenes-drive emitir 59 actualizar_ya --motivo "publicada 2.7.16"
    ordenes-drive emitir 59 resync --equipo GISSELAJAYA
    ordenes-drive ver 59
    ordenes-drive limpiar 59

Acciones permitidas (deliberadamente NO destructivas):
    sincronizar       una pasada ya, sin esperar los 5 minutos
    resync            rehacer la línea base de bisync
    actualizar_ya     comprobar e instalar la versión publicada, sin esperar 24 h
    recoger_registro  subir los registros del día ahora mismo
    reiniciar_app     cerrar y reabrir la app (no reinicia Windows)
    medir_carpeta     recontar la carpeta local para la ficha

Nada de borrar, desinstalar ni ejecutar comandos libres: si mañana hace falta
algo así, se decide aparte y con más garantías (ver PROPUESTA-PANEL-EQUIPOS-MASTER.md).
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta

RAIZ = '/mnt/almacen'
ACCIONES = ['sincronizar', 'resync', 'actualizar_ya', 'recoger_registro',
            'reiniciar_app', 'medir_carpeta']
HORAS_VIGENCIA = 48


def carpeta(usuario_id):
    ruta = os.path.join(RAIZ, str(usuario_id), 'archivos', '.registro-drive')
    if not os.path.isdir(ruta):
        sys.exit(f'No existe {ruta}: ¿ese usuario tiene la app instalada?')
    return ruta


def _dueno_sistemas(ruta):
    """Los archivos del Drive son de `sistemas:www-data`; si esto corre como
    root, dejarlo igual para que el servicio los lea y sirva sin sorpresas."""
    try:
        import pwd, grp
        os.chown(ruta, pwd.getpwnam('sistemas').pw_uid, grp.getgrnam('www-data').gr_gid)
    except (KeyError, PermissionError, OSError):
        pass


def _leer(ruta):
    try:
        with open(ruta, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def emitir(usuario_id, accion, equipo, motivo, horas):
    if accion not in ACCIONES:
        sys.exit(f'Acción no permitida: {accion}. Permitidas: {", ".join(ACCIONES)}')
    destino = os.path.join(carpeta(usuario_id), 'ordenes.json')
    ahora = datetime.now()
    datos = _leer(destino)
    pendientes = [o for o in datos.get('ordenes', [])
                  if o.get('caduca', '') > ahora.isoformat()]
    pendientes.append({
        'id': ahora.strftime('%Y%m%d-%H%M%S') + '-' + accion,
        'accion': accion,
        'equipo': equipo,                     # None = cualquier equipo de la persona
        'emitida': ahora.isoformat(timespec='seconds'),
        'caduca': (ahora + timedelta(hours=horas)).isoformat(timespec='seconds'),
        'motivo': motivo or '',
    })
    with open(destino, 'w', encoding='utf-8') as f:
        json.dump({'ordenes': pendientes}, f, ensure_ascii=False, indent=2)
    os.chmod(destino, 0o644)
    _dueno_sistemas(destino)
    print(f'Orden dejada en {destino}: {pendientes[-1]["id"]}')


def ver(usuario_id):
    car = carpeta(usuario_id)
    ordenes = _leer(os.path.join(car, 'ordenes.json')).get('ordenes', [])
    print(f'Órdenes pendientes: {len(ordenes)}')
    for o in ordenes:
        print(f'  {o["id"]} · equipo={o.get("equipo") or "cualquiera"} · caduca {o["caduca"]} · {o.get("motivo", "")}')
    resultados = _leer(os.path.join(car, 'ordenes-resultado.json')).get('resultados', [])
    print(f'Resultados informados por los equipos: {len(resultados)}')
    for r in resultados[-10:]:
        print(f'  {r.get("id")} · {r.get("equipo")} · {r.get("estado")} · {r.get("momento")} · {r.get("detalle", "")}')


def limpiar(usuario_id):
    destino = os.path.join(carpeta(usuario_id), 'ordenes.json')
    if os.path.exists(destino):
        os.remove(destino)
        print(f'Órdenes retiradas: {destino}')
    else:
        print('No había órdenes pendientes.')


def main():
    p = argparse.ArgumentParser(description='Órdenes para la app Drive Maquita de Windows.')
    sub = p.add_subparsers(dest='comando', required=True)

    e = sub.add_parser('emitir', help='dejar una orden a un usuario')
    e.add_argument('usuario_id', type=int)
    e.add_argument('accion', choices=ACCIONES)
    e.add_argument('--equipo', default=None, help='solo para ese equipo (por defecto, todos los suyos)')
    e.add_argument('--motivo', default='', help='queda escrito en la orden y en el registro')
    e.add_argument('--horas', type=int, default=HORAS_VIGENCIA, help=f'vigencia (por defecto {HORAS_VIGENCIA})')

    v = sub.add_parser('ver', help='ver órdenes pendientes y resultados')
    v.add_argument('usuario_id', type=int)

    l = sub.add_parser('limpiar', help='retirar las órdenes pendientes')
    l.add_argument('usuario_id', type=int)

    a = p.parse_args()
    if a.comando == 'emitir':
        emitir(a.usuario_id, a.accion, a.equipo, a.motivo, a.horas)
    elif a.comando == 'ver':
        ver(a.usuario_id)
    else:
        limpiar(a.usuario_id)


if __name__ == '__main__':
    main()
