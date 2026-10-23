"""
Eliminar UN elemento de la papelera («Eliminar definitivamente»).

El explorador y el Drive del webmail llaman a POST /papelera/eliminar, pero el servicio
solo tenía listar, restaurar y vaciar: el borrado individual respondía «Función no
disponible». Igual que vaciar, NO destruye: el elemento pasa a la retención de
RETENCION_DIAS (recuperable solo por master).

Aparte de nucleo_archivos.py para no engordarlo (ya pasa de 800 líneas).
"""
import logging
import os
import shutil

from almacen_bd import consultar, ejecutar
from seguridad_rutas import raiz_usuario

log = logging.getLogger('almacen.papelera')


def eliminar_de_papelera(usuario_id: int, nombre_fisico: str) -> bool:
    """Pasa a la retención el elemento `nombre_fisico` de la papelera del usuario.
    FileNotFoundError si no está en su papelera."""
    filas = consultar('SELECT * FROM papelera WHERE usuario_id = %s AND nombre_fisico = %s',
                      (usuario_id, nombre_fisico))
    if not filas:
        raise FileNotFoundError('No está en la papelera')
    fila = filas[0]
    origen = os.path.join(raiz_usuario(usuario_id, 'papelera'), fila['nombre_fisico'])
    destino = os.path.join(raiz_usuario(usuario_id, 'retencion'), fila['nombre_fisico'])
    if os.path.exists(origen):
        shutil.move(origen, destino)
    ejecutar("""
        INSERT INTO retencion (usuario_id, ruta_original, nombre, nombre_fisico,
                               es_carpeta, tamano_bytes)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (usuario_id, fila['ruta_original'], fila['nombre'], fila['nombre_fisico'],
          fila['es_carpeta'], fila['tamano_bytes']))
    ejecutar('DELETE FROM papelera WHERE id = %s', (fila['id'],))
    log.info('Elemento %s del usuario %s pasado a retención', nombre_fisico, usuario_id)
    return True
