# -*- coding: utf-8 -*-
"""
Espacios del índice del Almacén: de quién es cada fila y dónde puede buscar cada
persona.
=============================================================================
Los dos índices (`indice_busqueda`, de nombres, e `indice_contenido`, del texto)
guardan sus filas con una clave `(usuario_id, ruta)`. Hasta ahora ese
`usuario_id` era **quien hacía la operación**, no de quién es el archivo, y eso
traía dos problemas de verdad:

1. **Filas mal atribuidas.** Si alguien subía o abría un archivo de una unidad
   compartida (`/unidades/13/…`), la fila quedaba a su nombre. El índice de
   nombres lo disimulaba porque se reconstruye entero cada noche; el de
   contenido no se reconstruye nunca, así que el 27/08/2026 tenía 73.000 filas
   de unidades repartidas entre las personas que las habían tocado.
2. **Búsquedas que no encuentran.** Al buscar solo se miraba `usuario_id = yo`,
   de modo que **nada de las unidades compartidas ni de lo que otra persona me
   compartió salía en los resultados**, aunque lo tuviera delante en el
   explorador.

Este módulo pone una sola regla: **la fila del índice pertenece al ESPACIO donde
vive el archivo, no a quien lo tocó**, y al buscar se consultan los espacios a
los que esa persona tiene acceso HOY (se comprueba en cada búsqueda, no se
hereda de cuando se indexó).

    /unidades/<n>/…        → espacio 0 (las unidades compartidas, de la casa)
    /compartido/<dueño>/x  → espacio <dueño>, ruta «/x» (es SU archivo)
    cualquier otra         → espacio de la propia persona

La canonicalización de `/compartido/<dueño>/…` importa: el mismo archivo se ve
por dos caminos (el dueño lo tiene en «/x», quien lo recibe en
«/compartido/<dueño>/x») y sin esto se indexaría dos veces, con el riesgo de que
la copia ajena sobreviviera al día siguiente de retirarle el permiso.

Autoría: Equipo de Tecnología Maquita — 2026-08-27
"""
import logging

from permisos_compartidos import compartido_de_ruta
from seguridad_rutas import normalizar_ruta_virtual, unidad_de_ruta

log = logging.getLogger('almacen.espacios')

# Dueño-índice del contenido de las unidades compartidas. Es el mismo valor que
# `indice_busqueda.USUARIO_UNIDADES`; se define aquí para que este módulo no
# dependa de aquel (aquel sí depende de este).
ESPACIO_UNIDADES = 0


def espacio_de(usuario_id: int, ruta_virtual: str):
    """(espacio, ruta) con los que hay que guardar esta ruta en el índice.

    Es la función que decide de quién es la fila. Ante cualquier rareza se
    devuelve el par recibido: nunca se pierde la indexación por un fallo aquí.
    """
    try:
        limpia = normalizar_ruta_virtual(ruta_virtual)
    except Exception:
        return int(usuario_id), ruta_virtual

    try:
        propietario, subruta = compartido_de_ruta(limpia)
        if propietario is not None:
            # Lo compartido conmigo es del DUEÑO y se indexa en su espacio, con
            # su ruta de verdad: es el mismo archivo, no una copia mía.
            return int(propietario), subruta
    except Exception:
        pass

    try:
        unidad_id, _sub = unidad_de_ruta(limpia)
        if unidad_id is not None:
            return ESPACIO_UNIDADES, limpia
    except Exception:
        pass

    return int(usuario_id), limpia


def espacios_de_busqueda(usuario_id: int) -> list:
    """Espacios donde esta persona puede buscar AHORA MISMO.

    Devuelve una lista de dicts con:
        espacio  — usuario_id de las filas del índice que hay que mirar
        prefijo  — None (todo el espacio) o el prefijo de ruta al que se limita
        visible  — prefijo con el que hay que devolver la ruta al explorador
                   ('' cuando la ruta ya es la que la persona ve)

    El permiso se resuelve aquí y ahora. Si algo falla al calcular un espacio
    añadido, se descarta ESE espacio y se sigue con los demás: una unidad que no
    se pueda comprobar no sale en los resultados (falla cerrado), pero la
    búsqueda en la unidad propia nunca se queda sin funcionar.
    """
    usuario_id = int(usuario_id)
    espacios = [{'espacio': usuario_id, 'prefijo': None, 'visible': ''}]
    espacios.extend(_espacios_de_unidades(usuario_id))
    espacios.extend(_espacios_compartidos(usuario_id))
    return espacios


def _espacios_de_unidades(usuario_id: int) -> list:
    """Un espacio por cada unidad compartida donde la persona es miembro.

    Se limita por prefijo `/unidades/<id>/`: ser miembro de la unidad 9 no puede
    dar resultados de la 13, aunque las filas de las dos vivan bajo el espacio 0.
    """
    try:
        from almacen_bd import consultar, es_master
        if es_master(usuario_id):
            filas = consultar('SELECT id FROM unidades_compartidas')
        else:
            filas = consultar(
                'SELECT unidad_id AS id FROM unidad_miembros WHERE usuario_id = %s',
                (usuario_id,))
    except Exception as excepcion:
        log.warning('espacios: no se pudieron leer las unidades de %s: %s',
                    usuario_id, excepcion)
        return []
    return [{'espacio': ESPACIO_UNIDADES,
             'prefijo': '/unidades/%d/' % int(fila['id']),
             'visible': ''}
            for fila in filas]


def _espacios_compartidos(usuario_id: int) -> list:
    """Un espacio por cada carpeta o archivo que otra persona me compartió.

    La ruta indexada es la del dueño («/Proyectos/x.pdf»), pero quien busca solo
    puede abrirla por su camino («/compartido/53/Proyectos/x.pdf»), así que se
    devuelve también el prefijo con el que hay que enseñarla.

    Se salta lo protegido con clave: ese acceso se gana en la vista del enlace,
    no por el explorador — la misma regla que `permisos_compartidos`.
    """
    try:
        from permisos_compartidos import concesiones
        recibidas = concesiones(usuario_id)
    except Exception as excepcion:
        log.warning('espacios: no se pudieron leer los compartidos de %s: %s',
                    usuario_id, excepcion)
        return []

    espacios = []
    for concesion in recibidas:
        if concesion.get('clave_hash'):
            continue
        try:
            dueno = int(concesion['propietario_id'])
            ruta = normalizar_ruta_virtual(concesion['ruta'])
        except Exception:
            continue
        espacios.append({
            'espacio': dueno,
            # La raíz compartida no lleva prefijo: cubre todo el espacio del dueño.
            'prefijo': None if ruta == '/' else ruta,
            'visible': '/compartido/%d' % dueno,
        })
    return espacios


def condicion_sql(espacios: list):
    """(fragmento SQL, parámetros) que limita una consulta a esos espacios.

    El fragmento se pega con AND y ya viene entre paréntesis. Una ruta se acepta
    si es el prefijo exacto o cuelga de él, comparando por segmentos completos
    para que «/Cacao» no arrastre «/Cacao Privado».
    """
    trozos, parametros = [], []
    for uno in espacios:
        prefijo = uno.get('prefijo')
        if not prefijo or prefijo == '/':
            trozos.append('(usuario_id = %s)')
            parametros.append(int(uno['espacio']))
        else:
            limpio = prefijo.rstrip('/')
            trozos.append('(usuario_id = %s AND (ruta = %s OR ruta LIKE %s))')
            parametros.extend([int(uno['espacio']), limpio, limpio + '/%'])
    if not trozos:
        return '(false)', []
    return '(' + ' OR '.join(trozos) + ')', parametros


def ruta_visible(espacios: list, espacio: int, ruta: str) -> str:
    """Ruta con la que hay que devolver un resultado al explorador.

    Lo que está en el espacio de otra persona solo se puede abrir por
    «/compartido/<dueño>/…»; devolver la ruta cruda del dueño daría un enlace
    que no lleva a ninguna parte.
    """
    for uno in espacios:
        if int(uno['espacio']) != int(espacio):
            continue
        prefijo = uno.get('prefijo')
        if prefijo and prefijo != '/':
            limpio = prefijo.rstrip('/')
            if ruta != limpio and not ruta.startswith(limpio + '/'):
                continue
        visible = uno.get('visible') or ''
        return (visible + ruta) if visible else ruta
    return ruta
