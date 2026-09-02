# -*- coding: utf-8 -*-
"""
Migrador POR LOTES Nextcloud -> Almacén (un solo proceso).
==========================================================
Evita el costo de arranque de FARO por-usuario: importa UNA vez y recorre la
lista de usuarios. Por cada usuario: copia sus archivos de la Nube (WebDAV) al
disco del Almacén y LUEGO reconstruye su índice (reindexar_usuario), sin el cual
los archivos migrados no se verían en el explorador.

Reanudable: escribe un marcador por usuario en <estado_dir>/<uid>.ok y lo salta
si ya está. Log detallado por usuario en stdout (redirigir a archivo).

Uso:
  python3 migrar_lote.py <archivo_uids> [estado_dir]
    <archivo_uids>: un uid FARO por línea (se ignoran líneas vacías / '#').
Autoría: Equipo de Tecnología Maquita — 2026-07-23
"""
import os
import sys
import time

sys.path.insert(0, '/home/sistemas/Maquita')
sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')

from modulos.nextcloud.interfaces.api.nextcloud_api import get_servicio  # noqa
from modulos.nextcloud.infraestructura.persistencia.repositorio_credenciales import repositorio_credenciales  # noqa
from seguridad_rutas import ruta_fisica  # noqa
import indice_busqueda  # noqa
from migrar_desde_nextcloud import recorrer, _humano  # noqa


def migrar_usuario(webdav, uid):
    cred = repositorio_credenciales.obtener_credencial(uid)
    if not cred:
        print(f'[{uid}] SIN credencial de Nextcloud — se omite', flush=True)
        return None
    usuario_nc = cred[0]
    t0 = time.monotonic()
    arch = bytes_ = carp = copiados = errores = 0
    print(f'[{uid}] Migrando Nube de "{usuario_nc}"...', flush=True)
    for ruta, es_carpeta, tam in recorrer(webdav, usuario_nc, '/'):
        if es_carpeta:
            carp += 1
            os.makedirs(ruta_fisica(uid, ruta), exist_ok=True)
            continue
        arch += 1
        bytes_ += tam
        try:
            datos = webdav.descargar_archivo(usuario_nc, ruta)
            destino = ruta_fisica(uid, ruta)
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            with open(destino, 'wb') as f:
                f.write(datos)
            copiados += 1
            if copiados % 100 == 0:
                print(f'[{uid}]   ... {copiados} archivos ({_humano(bytes_)})', flush=True)
        except Exception as e:
            errores += 1
            print(f'[{uid}]   ! error copiando {ruta}: {e}', flush=True)
    # Reindexado: sin esto los archivos migrados NO aparecen en el explorador.
    try:
        elementos = indice_busqueda.reindexar_usuario(uid)
    except Exception as e:
        elementos = -1
        print(f'[{uid}]   ! error reindexando: {e}', flush=True)
    dt = time.monotonic() - t0
    print(f'[{uid}] OK carpetas={carp} archivos={arch} copiados={copiados} '
          f'errores={errores} tam={_humano(bytes_)} indexados={elementos} '
          f'en {dt:.0f}s', flush=True)
    return {'copiados': copiados, 'errores': errores, 'indexados': elementos}


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    lista = sys.argv[1]
    estado_dir = sys.argv[2] if len(sys.argv) > 2 else '/tmp/mig_estado'
    os.makedirs(estado_dir, exist_ok=True)
    uids = []
    for l in open(lista):
        l = l.strip()
        if l and not l.startswith('#'):
            uids.append(int(l.split('|')[0]))
    webdav = get_servicio().webdav
    print(f'== LOTE: {len(uids)} usuarios · estado en {estado_dir} ==', flush=True)
    ok = fallidos = saltados = 0
    for i, uid in enumerate(uids, 1):
        marca = os.path.join(estado_dir, f'{uid}.ok')
        if os.path.exists(marca):
            saltados += 1
            print(f'[{uid}] ya migrado ({i}/{len(uids)}) — se salta', flush=True)
            continue
        print(f'--- ({i}/{len(uids)}) usuario {uid} ---', flush=True)
        r = migrar_usuario(webdav, uid)
        if r is not None and r['indexados'] >= 0:
            open(marca, 'w').write(f"{r}")
            ok += 1
        else:
            fallidos += 1
    print(f'== FIN LOTE: ok={ok} fallidos={fallidos} saltados={saltados} ==', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
