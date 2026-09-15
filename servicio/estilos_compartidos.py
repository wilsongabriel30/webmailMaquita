"""Drive Maquita — color/icono de carpeta COMPARTIDO en las unidades (14/09/2026).

Problema: `estilos_carpeta` guarda (usuario_id, folder_id) y folder_id es un
hash de «usuario:ruta». En una unidad compartida cada persona veía solo los
colores que ELLA puso; los que pintaba el administrador no los veía nadie más.

Regla nueva: dentro de `/unidades/<id>/...` el estilo es de la CARPETA, no de
la persona: se guarda con usuario_id = 0 y folder_id = hash('0:ruta'). Fuera
de las unidades (Mi unidad) sigue siendo personal, como siempre.

También se reubica el estilo cuando la carpeta se renombra o se mueve, para
que el color no se pierda al cambiarle el nombre.
"""
import hashlib
import re

from almacen_bd import consultar, ejecutar

USUARIO_COMPARTIDO = 0
_RE_UNIDAD = re.compile(r'^/unidades/\d+(/.*)?$')


def _hash(usuario_id, ruta_virtual):
    return hashlib.sha1(f'{usuario_id}:{ruta_virtual}'.encode('utf-8')).hexdigest()[:16]


def es_de_unidad(ruta_virtual):
    return bool(_RE_UNIDAD.match(ruta_virtual or ''))


def clave(usuario_id, ruta_virtual):
    """(usuario_id, folder_id) con el que se guarda el estilo de esa carpeta."""
    if es_de_unidad(ruta_virtual):
        return USUARIO_COMPARTIDO, _hash(USUARIO_COMPARTIDO, ruta_virtual)
    return usuario_id, _hash(usuario_id, ruta_virtual)


def estilos_de_unidad():
    """Todos los estilos compartidos, por folder_id (para listar)."""
    return {e['folder_id']: e for e in consultar(
        'SELECT folder_id, color, icono FROM estilos_carpeta WHERE usuario_id = %s',
        (USUARIO_COMPARTIDO,))}


def folder_id_compartido(ruta_virtual):
    return _hash(USUARIO_COMPARTIDO, ruta_virtual)


def reubicar(usuario_id, ruta_vieja, ruta_nueva):
    """La carpeta cambió de ruta (renombrar/mover): el estilo la sigue."""
    try:
        for uid, viejo in {clave(usuario_id, ruta_vieja),
                           (usuario_id, _hash(usuario_id, ruta_vieja))}:
            uid_nuevo, nuevo = clave(usuario_id, ruta_nueva) if uid == USUARIO_COMPARTIDO \
                else (usuario_id, _hash(usuario_id, ruta_nueva))
            filas = consultar('SELECT color, icono FROM estilos_carpeta '
                              'WHERE usuario_id = %s AND folder_id = %s', (uid, viejo))
            if not filas:
                continue
            ejecutar('INSERT INTO estilos_carpeta (usuario_id, folder_id, color, icono) '
                     'VALUES (%s, %s, %s, %s) ON CONFLICT (usuario_id, folder_id) '
                     'DO UPDATE SET color = EXCLUDED.color, icono = EXCLUDED.icono',
                     (uid_nuevo, nuevo, filas[0]['color'], filas[0]['icono']))
            ejecutar('DELETE FROM estilos_carpeta WHERE usuario_id = %s AND folder_id = %s',
                     (uid, viejo))
    except Exception:      # el estilo nunca debe impedir un renombrado
        pass
