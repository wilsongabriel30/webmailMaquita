# -*- coding: utf-8 -*-
"""
Migrador de REASIGNACIÓN de cuenta Nextcloud → espacio de OTRO usuario del Almacén.
==================================================================================
Para cuentas cuyo dueño NC no coincide con el uid destino: cuentas de gerencia
que se fusionan en la persona actual, o ex-empleados cuyo contenido pasa a un
empleado vigente. Copia la cuenta NC de origen al espacio del uid destino,
opcionalmente bajo una subcarpeta, y reindexa el destino.

Lee "trabajos" de un archivo: una línea por trabajo con formato
    <cuenta_nc_origen>|<uid_destino>|<subcarpeta_opcional>
(subcarpeta vacía = fusionar en la raíz del destino).

Uso:
  python3 migrar_cuenta.py <archivo_trabajos> [estado_dir]
Autoría: Equipo de Tecnología Maquita — 2026-07-23
"""
import os
import sys
import time

sys.path.insert(0, '/home/sistemas/Maquita')
sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')

from modulos.nextcloud.interfaces.api.nextcloud_api import get_servicio  # noqa
from seguridad_rutas import ruta_fisica  # noqa
import indice_busqueda  # noqa
from migrar_desde_nextcloud import recorrer, _humano  # noqa


def _destino_virtual(prefijo, ruta):
    """Une la subcarpeta destino con la ruta original de la Nube."""
    if not prefijo:
        return ruta
    p = '/' + prefijo.strip('/')
    return p + ruta  # ruta ya empieza con '/'


def migrar_cuenta(webdav, origen_nc, uid, prefijo):
    t0 = time.monotonic()
    arch = bytes_ = carp = copiados = errores = 0
    destino_txt = f'uid {uid}' + (f' /{prefijo.strip("/")}' if prefijo else ' (raíz, fusión)')
    print(f'[{origen_nc}→{destino_txt}] Copiando...', flush=True)
    for ruta, es_carpeta, tam in recorrer(webdav, origen_nc, '/'):
        virtual = _destino_virtual(prefijo, ruta)
        if es_carpeta:
            carp += 1
            os.makedirs(ruta_fisica(uid, virtual), exist_ok=True)
            continue
        arch += 1
        bytes_ += tam
        try:
            datos = webdav.descargar_archivo(origen_nc, ruta)
            destino = ruta_fisica(uid, virtual)
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            with open(destino, 'wb') as f:
                f.write(datos)
            copiados += 1
            if copiados % 100 == 0:
                print(f'[{origen_nc}]   ... {copiados} archivos ({_humano(bytes_)})', flush=True)
        except Exception as e:
            errores += 1
            print(f'[{origen_nc}]   ! error {ruta}: {e}', flush=True)
    dt = time.monotonic() - t0
    print(f'[{origen_nc}→{destino_txt}] OK carpetas={carp} archivos={arch} '
          f'copiados={copiados} errores={errores} tam={_humano(bytes_)} en {dt:.0f}s',
          flush=True)
    return uid


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    lista = sys.argv[1]
    estado_dir = sys.argv[2] if len(sys.argv) > 2 else '/tmp/mig_cuenta_estado'
    os.makedirs(estado_dir, exist_ok=True)
    trabajos = []
    for l in open(lista):
        l = l.strip()
        if not l or l.startswith('#'):
            continue
        partes = l.split('|')
        origen = partes[0].strip()
        uid = int(partes[1])
        prefijo = partes[2].strip() if len(partes) > 2 else ''
        trabajos.append((origen, uid, prefijo))
    webdav = get_servicio().webdav
    print(f'== REASIGNACIÓN: {len(trabajos)} cuentas ==', flush=True)
    afectados = set()
    for origen, uid, prefijo in trabajos:
        marca = os.path.join(estado_dir, f'{origen}.ok')
        if os.path.exists(marca):
            print(f'[{origen}] ya migrado — se salta', flush=True)
            afectados.add(uid)
            continue
        try:
            migrar_cuenta(webdav, origen, uid, prefijo)
            open(marca, 'w').write('ok')
            afectados.add(uid)
        except Exception as e:
            print(f'[{origen}] FALLÓ: {e}', flush=True)
    # Reindexar UNA vez cada uid destino afectado (tras fusionar todo su contenido)
    for uid in sorted(afectados):
        try:
            n = indice_busqueda.reindexar_usuario(uid)
            print(f'[reindex uid {uid}] {n} elementos', flush=True)
        except Exception as e:
            print(f'[reindex uid {uid}] ERROR: {e}', flush=True)
    print('== FIN REASIGNACIÓN ==', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
