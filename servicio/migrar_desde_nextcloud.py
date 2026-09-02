# -*- coding: utf-8 -*-
"""
Migrador Nextcloud -> Almacén Maquita.
======================================
Copia los archivos de la Nube (Nextcloud) de un usuario a su espacio en el Almacén,
preservando la estructura de carpetas. Usa el cliente WebDAV de FARO para leer NC
y escribe directo en el disco del Almacén (respeta la ruta virtual del usuario).

Uso:
  python3 migrar_desde_nextcloud.py <usuario_faro_id> contar     # solo cuenta (dry-run)
  python3 migrar_desde_nextcloud.py <usuario_faro_id> migrar     # copia de verdad
  python3 migrar_desde_nextcloud.py <usuario_faro_id> migrar 2   # límite en GB (opcional)

Autoría: Equipo de Tecnología Maquita — 2026-07-03
"""
import os
import sys

sys.path.insert(0, '/home/sistemas/Maquita')                       # FARO (cliente NC)
sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')      # Almacén

from modulos.nextcloud.interfaces.api.nextcloud_api import get_servicio  # noqa
from modulos.nextcloud.infraestructura.persistencia.repositorio_credenciales import repositorio_credenciales  # noqa
from seguridad_rutas import ruta_fisica  # noqa


def _humano(n):
    n = float(n or 0)
    for u in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024 or u == 'TB':
            return f'{n:.1f} {u}'
        n /= 1024


def recorrer(webdav, usuario_nc, ruta):
    """Genera (ruta, es_carpeta, tamano) de todo el árbol NC bajo 'ruta'."""
    try:
        carpetas, archivos = webdav.listar_directorio(usuario_nc, ruta)
    except Exception as e:
        print(f'  ! no se pudo listar {ruta}: {e}')
        return
    for a in archivos:
        yield (a.ruta, False, getattr(a, 'tamano_bytes', 0) or 0)
    for c in carpetas:
        yield (c.ruta, True, 0)
        yield from recorrer(webdav, usuario_nc, c.ruta)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    uid = int(sys.argv[1])
    modo = sys.argv[2]
    limite_bytes = float(sys.argv[3]) * 1024 ** 3 if len(sys.argv) > 3 else None

    cred = repositorio_credenciales.obtener_credencial(uid)
    if not cred:
        print(f'El usuario {uid} no tiene credenciales de Nextcloud')
        return 1
    usuario_nc = cred[0]
    webdav = get_servicio().webdav

    total_arch = total_bytes = total_carp = copiados = 0
    print(f'Recorriendo la Nube de "{usuario_nc}" (usuario FARO {uid})...')
    for ruta, es_carpeta, tam in recorrer(webdav, usuario_nc, '/'):
        if es_carpeta:
            total_carp += 1
            if modo == 'migrar':
                os.makedirs(ruta_fisica(uid, ruta), exist_ok=True)
            continue
        total_arch += 1
        total_bytes += tam
        if modo == 'migrar':
            if limite_bytes and total_bytes > limite_bytes:
                print(f'  (límite de {_humano(limite_bytes)} alcanzado, se detiene)')
                break
            try:
                datos = webdav.descargar_archivo(usuario_nc, ruta)
                destino = ruta_fisica(uid, ruta)
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                with open(destino, 'wb') as f:
                    f.write(datos)
                copiados += 1
                if copiados % 25 == 0:
                    print(f'  ... {copiados} archivos copiados ({_humano(total_bytes)})')
            except Exception as e:
                print(f'  ! error copiando {ruta}: {e}')

    print('─' * 50)
    print(f'Carpetas: {total_carp} · Archivos: {total_arch} · Tamaño: {_humano(total_bytes)}')
    if modo == 'migrar':
        print(f'COPIADOS al Almacén: {copiados} archivos')
    else:
        print('(solo conteo — usa "migrar" para copiar)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
