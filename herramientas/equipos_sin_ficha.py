#!/usr/bin/env python3
"""Equipos que usan el Drive pero NO mandan ficha de estado.

Los equipos en modo «en vivo» (sin copia local) y los que llevan una versión
anterior a la 2.7.4 no escriben `.registro-drive/estado-<EQUIPO>.json`: en el
informe de flota no aparecen, y desde soporte no se sabe si están vivos. Esto
tapa el hueco con lo único que el servidor sí sabe de ellos: **cuándo fue la
última vez que su token habló con el WebDAV**.

No sustituye a la ficha (no da versión, ni errores, ni sincronización): sirve
para saber que el equipo está conectado y desde cuándo no aparece.

    drive-equipos-sin-ficha            # todos
    drive-equipos-sin-ficha --dias 3   # solo los que llevan más de 3 días sin hablar
"""
import argparse
import glob
import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')
ALMACEN = '/mnt/almacen'


def usuarios_con_ficha():
    """{usuario_id: (equipo, version, momento)} de quienes sí mandan ficha."""
    fichas = {}
    for ruta in glob.glob(os.path.join(ALMACEN, '*', 'archivos', '.registro-drive', 'estado-*.json')):
        try:
            with open(ruta, encoding='utf-8') as f:
                d = json.load(f)
            fichas.setdefault(str(d.get('usuario_faro')), []).append(
                (d.get('equipo'), d.get('version'), d.get('momento')))
        except (OSError, ValueError):
            continue
    return fichas


def tokens_vivos():
    from almacen_bd import consultar
    return consultar("""
        SELECT usuario_id, nombre, ultimo_uso, ultima_ip
        FROM dav_tokens
        WHERE revocado IS NULL AND ultimo_uso IS NOT NULL
        ORDER BY ultimo_uso DESC
    """)


def main():
    p = argparse.ArgumentParser(description='Equipos que usan el Drive y no mandan ficha de estado.')
    p.add_argument('--dias', type=float, default=None,
                   help='mostrar solo los que llevan más de N días sin hablar con el servidor')
    a = p.parse_args()

    fichas = usuarios_con_ficha()
    ahora = datetime.now()
    filas = []
    for t in tokens_vivos():
        usuario = str(t['usuario_id'])
        if usuario in fichas:          # ese usuario sí manda ficha: no es un hueco
            continue
        silencio = ahora - t['ultimo_uso']
        if a.dias is not None and silencio < timedelta(days=a.dias):
            continue
        filas.append((usuario, t['nombre'], t['ultimo_uso'], silencio, t['ultima_ip']))

    if not filas:
        print('Todos los equipos con token activo mandan ficha de estado.')
        return
    print('EQUIPOS SIN FICHA (modo «en vivo» o versión anterior a la 2.7.4)')
    print('No se puede saber su versión ni si sincronizan; solo cuándo hablaron por última vez.\n')
    print('%-7s %-34s %-20s %s' % ('USUARIO', 'NOMBRE DEL TOKEN', 'ÚLTIMA VEZ', 'SILENCIO'))
    print('-' * 88)
    for usuario, nombre, ultimo, silencio, _ip in filas:
        horas = silencio.total_seconds() / 3600
        cuanto = f'{horas:.1f} h' if horas < 48 else f'{horas / 24:.1f} días'
        print('u%-6s %-34s %-20s %s' % (usuario, (nombre or '')[:34],
                                        ultimo.strftime('%d/%m %H:%M'), cuanto))


if __name__ == '__main__':
    main()
