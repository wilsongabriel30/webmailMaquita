# -*- coding: utf-8 -*-
"""«Sin acceso a esta carpeta»: bloqueos por persona dentro de una unidad compartida.

Responsabilidad ÚNICA: guardar, consultar y aplicar los bloqueos por carpeta. Sin Flask
(lo usa también el disco montado, que corre aparte).

POR QUÉ (26/11/2026, pedido de Wilson): el modelo de permisos de las unidades es ampliativo
(una concesión por carpeta solo SUBE el nivel; ver `permisos_unidad_carpeta`). Para que una
persona deje de ver UNA carpeta había que sacarla de toda la unidad. Ahora un administrador
de la unidad puede quitarle el acceso solo a esa carpeta (y a lo que contiene).

REGLAS
  1. Un administrador de la unidad (o el master del Drive) NUNCA queda bloqueado.
  2. El bloqueo se hereda hacia abajo: bloquear `/Esmeraldas` alcanza a `/Esmeraldas/2026/x.docx`.
  3. Dentro de una carpeta bloqueada se puede volver a abrir una subcarpeta concreta con una
     concesión por carpeta MÁS PROFUNDA que el bloqueo. Una concesión en la misma carpeta o
     en una superior no lo anula: bloquear borra las concesiones de esa persona en la carpeta
     y en lo que contiene, y conceder en la carpeta bloqueada quita el bloqueo.
  4. Lo bloqueado no se ve: no sale en el listado, la búsqueda, favoritos, recientes, la
     papelera de la unidad ni el disco montado. Tampoco se puede descargar en ZIP, copiar,
     mover ni borrar una carpeta que contenga algo bloqueado para esa persona.
  5. Falla CERRADO: si no se puede comprobar el bloqueo, quien no es administrador no entra.
"""

import logging

from almacen_bd import consultar, ejecutar

log = logging.getLogger('almacen.bloqueos_carpeta')

_TABLA = """
    CREATE TABLE IF NOT EXISTS unidad_bloqueos_carpeta (
        unidad_id INTEGER NOT NULL,
        ruta TEXT NOT NULL,                 -- relativa a la unidad, p. ej. /Esmeraldas
        usuario_id INTEGER NOT NULL,
        creado_por INTEGER,
        creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (unidad_id, ruta, usuario_id)
    );
    CREATE INDEX IF NOT EXISTS idx_ubc_usuario ON unidad_bloqueos_carpeta(usuario_id, unidad_id);
"""


def asegurar_esquema():
    ejecutar(_TABLA)


def _norm(sub):
    return '/' + (sub or '').strip('/')


def _cubre(base, sub):
    """¿`base` es `sub` o una carpeta que lo contiene? (por segmentos completos)."""
    base, sub = _norm(base), _norm(sub)
    return base == '/' or sub == base or sub.startswith(base + '/')


def _rango(rol):
    return {'viewer': 1, 'editor': 2, 'manager': 3}.get(rol or '', 0)


def bloqueos_de(usuario_id, unidad_id):
    """Rutas bloqueadas para esa persona en esa unidad (lanza si la BD falla)."""
    return [f['ruta'] for f in consultar(
        'SELECT ruta FROM unidad_bloqueos_carpeta WHERE unidad_id = %s AND usuario_id = %s',
        (int(unidad_id), int(usuario_id)))]


def _concesiones(usuario_id, unidad_id):
    return [(f['ruta'], f['rol']) for f in consultar(
        'SELECT ruta, rol FROM unidad_permisos_carpeta WHERE unidad_id = %s AND usuario_id = %s',
        (int(unidad_id), int(usuario_id)))]


def resolver(sub, bloqueos, concesiones):
    """(bloqueado, rol_reabierto) para `sub` con los datos ya leídos. Puro, sin BD.

    bloqueado=False → no hay bloqueo que lo cubra (manda el cálculo normal).
    bloqueado=True  → solo entra con `rol_reabierto` (concesión más profunda que el bloqueo), o None.
    """
    que_cubren = [b for b in bloqueos if _cubre(b, sub)]
    if not que_cubren:
        return False, None
    profundo = max(que_cubren, key=lambda b: len(_norm(b)))
    mejor = None
    for ruta, rol in concesiones:
        if len(_norm(ruta)) > len(_norm(profundo)) and _cubre(profundo, ruta) and _cubre(ruta, sub):
            if _rango(rol) > _rango(mejor):
                mejor = rol
    return True, mejor


def aplicar(usuario_id, unidad_id, sub, rol_calculado, rol_de_unidad):
    """Rol final teniendo en cuenta los bloqueos. Lo llama `rol_efectivo`.

    Administrador de la unidad → sin cambios. Si la consulta falla → None (cerrado).
    """
    if rol_de_unidad == 'manager':
        return rol_calculado
    try:
        bloqueos = bloqueos_de(usuario_id, unidad_id)
        if not bloqueos:
            return rol_calculado
        bloqueado, reabierto = resolver(sub, bloqueos, _concesiones(usuario_id, unidad_id))
    except Exception as excepcion:
        log.error('No se pudo comprobar el bloqueo (usuario %s, unidad %s, %s): %s',
                  usuario_id, unidad_id, sub, excepcion)
        return None
    return reabierto if bloqueado else rol_calculado


# ── Visibilidad (listados, búsqueda, ZIP…) ─────────────────────────────────────

def _unidad(ruta_virtual):
    from seguridad_rutas import unidad_de_ruta
    return unidad_de_ruta(ruta_virtual)


def _es_admin(usuario_id, unidad_id):
    from roles_unidad import rol_en_unidad
    return rol_en_unidad(usuario_id, unidad_id) == 'manager'


def puede_ver(usuario_id, ruta_virtual):
    """¿La ruta NO está bloqueada para esa persona? Rutas fuera de unidades: True."""
    unidad_id, sub = _unidad(ruta_virtual)
    if unidad_id is None:
        return True
    try:
        if _es_admin(usuario_id, unidad_id):
            return True
        bloqueos = bloqueos_de(usuario_id, unidad_id)
        if not bloqueos:
            return True
        bloqueado, reabierto = resolver(sub, bloqueos, _concesiones(usuario_id, unidad_id))
        return (not bloqueado) or bool(reabierto)
    except Exception as excepcion:
        log.error('puede_ver falló (usuario %s, %s): %s', usuario_id, ruta_virtual, excepcion)
        return False


def filtrar_items(usuario_id, items, clave='ruta'):
    """Quita de una lista de elementos del explorador los que están bloqueados.

    Lee los bloqueos una sola vez por unidad. Si algo falla, quita los de unidades
    (cerrado) y deja los personales.
    """
    cache = {}
    salida = []
    for item in items or []:
        ruta = item.get(clave) or item.get('ruta_completa') or ''
        try:
            unidad_id, sub = _unidad(ruta)
        except Exception:
            unidad_id, sub = None, ruta
        if unidad_id is None:
            salida.append(item)
            continue
        if unidad_id not in cache:
            try:
                if _es_admin(usuario_id, unidad_id):
                    cache[unidad_id] = None
                else:
                    cache[unidad_id] = (bloqueos_de(usuario_id, unidad_id),
                                        _concesiones(usuario_id, unidad_id))
            except Exception as excepcion:
                log.error('filtrar_items: unidad %s: %s', unidad_id, excepcion)
                cache[unidad_id] = 'error'
        datos = cache[unidad_id]
        if datos is None or (datos != 'error' and not datos[0]):
            salida.append(item)
            continue
        if datos == 'error':
            continue
        bloqueado, reabierto = resolver(sub, datos[0], datos[1])
        if (not bloqueado) or reabierto:
            salida.append(item)
    return salida


def hay_bloqueo_debajo(usuario_id, ruta_virtual):
    """¿Hay algo bloqueado para esa persona en esa carpeta o dentro de ella?"""
    unidad_id, sub = _unidad(ruta_virtual)
    if unidad_id is None:
        return False
    if _es_admin(usuario_id, unidad_id):
        return False
    return any(_cubre(sub, b) for b in bloqueos_de(usuario_id, unidad_id))


def exigir_sin_bloqueo_debajo(usuario_id, ruta_virtual, accion):
    """Para copiar, mover, borrar o descargar en ZIP una carpeta: si contiene algo que esa
    persona no puede ver, se niega (si no, se llevaría o destruiría lo que no le toca)."""
    from seguridad_rutas import RutaInvalida
    try:
        hay = hay_bloqueo_debajo(usuario_id, ruta_virtual)
    except Exception as excepcion:
        log.error('exigir_sin_bloqueo_debajo falló (%s, %s): %s', usuario_id, ruta_virtual, excepcion)
        hay = True
    if hay:
        raise RutaInvalida('No se puede %s: la carpeta contiene elementos a los que usted no '
                           'tiene acceso.' % accion, codigo=403)


def rutas_excluidas(usuario_id, unidad_id):
    """Rutas virtuales completas (/unidades/<id>/…) que la búsqueda debe excluir.
    Las subcarpetas reabiertas dentro de un bloqueo no salen en la búsqueda (cerrado)."""
    if _es_admin(usuario_id, unidad_id):
        return []
    return ['/unidades/%d%s' % (int(unidad_id), _norm(b)) for b in bloqueos_de(usuario_id, unidad_id)]


# ── Gestión (la API exige administrador de la unidad) ──────────────────────────

def bloquear(unidad_id, ruta, usuario_id, creado_por=None):
    ruta = _norm(ruta)
    if ruta == '/':
        raise ValueError('Para quitar el acceso a toda la unidad, quítelo de la unidad.')
    if _es_admin(usuario_id, unidad_id):
        raise ValueError('A un administrador de la unidad no se le puede quitar el acceso a una carpeta.')
    ejecutar(
        "INSERT INTO unidad_bloqueos_carpeta (unidad_id, ruta, usuario_id, creado_por) "
        "VALUES (%s, %s, %s, %s) ON CONFLICT (unidad_id, ruta, usuario_id) DO UPDATE SET "
        "creado_por = EXCLUDED.creado_por, creado_en = NOW()",
        (int(unidad_id), ruta, int(usuario_id), int(creado_por) if creado_por else None))
    # Sus concesiones en esa carpeta y dentro dejan de valer: se quitan (regla 3).
    ejecutar(
        "DELETE FROM unidad_permisos_carpeta WHERE unidad_id = %s AND usuario_id = %s "
        "AND (ruta = %s OR ruta LIKE %s)",
        (int(unidad_id), int(usuario_id), ruta, ruta.replace('%', r'\%').replace('_', r'\_') + '/%'))
    return {'unidad_id': int(unidad_id), 'ruta': ruta, 'usuario_id': int(usuario_id)}


def desbloquear(unidad_id, ruta, usuario_id):
    ejecutar("DELETE FROM unidad_bloqueos_carpeta WHERE unidad_id = %s AND ruta = %s AND usuario_id = %s",
             (int(unidad_id), _norm(ruta), int(usuario_id)))
    return True


def quitar_por_concesion(unidad_id, ruta, usuario_id):
    """Conceder en la MISMA carpeta bloqueada quita el bloqueo (regla 3). Una concesión en una
    carpeta superior no lo anula; una más profunda reabre solo esa subcarpeta."""
    desbloquear(unidad_id, ruta, usuario_id)


def listar_para_carpeta(unidad_id, ruta):
    """Bloqueos que afectan a esa carpeta: los de ella misma y los heredados de una superior."""
    ruta = _norm(ruta)
    filas = consultar('SELECT ruta, usuario_id, creado_por, creado_en FROM unidad_bloqueos_carpeta '
                      'WHERE unidad_id = %s', (int(unidad_id),))
    salida = []
    for f in filas:
        if _cubre(f['ruta'], ruta):
            salida.append({'ruta': f['ruta'], 'usuario_id': int(f['usuario_id']),
                           'heredado': _norm(f['ruta']) != ruta,
                           'creado_en': f['creado_en'].isoformat() if f['creado_en'] else None})
    return salida


def reubicar(ruta_vieja, ruta_nueva):
    """El bloqueo sigue a la carpeta al renombrarla o moverla (si no, renombrar la abriría).

    Dentro de la misma unidad o hacia otra unidad se conserva; si sale de las unidades, deja
    de tener sentido y se borra. Nunca lanza: registra el error.
    """
    try:
        u_v, s_v = _unidad(ruta_vieja)
        if u_v is None:
            return
        u_n, s_n = _unidad(ruta_nueva)
        s_v = _norm(s_v)
        patron = s_v.replace('%', r'\%').replace('_', r'\_') + '/%'
        filas = consultar('SELECT ruta, usuario_id FROM unidad_bloqueos_carpeta WHERE unidad_id = %s '
                          'AND (ruta = %s OR ruta LIKE %s)', (int(u_v), s_v, patron))
        for f in filas:
            ejecutar('DELETE FROM unidad_bloqueos_carpeta WHERE unidad_id = %s AND ruta = %s AND usuario_id = %s',
                     (int(u_v), f['ruta'], int(f['usuario_id'])))
            if u_n is None:
                log.warning('Bloqueo %s (usuario %s) retirado: la carpeta salió de la unidad',
                            f['ruta'], f['usuario_id'])
                continue
            nueva = _norm(s_n) + f['ruta'][len(s_v):]
            ejecutar("INSERT INTO unidad_bloqueos_carpeta (unidad_id, ruta, usuario_id) VALUES (%s, %s, %s) "
                     "ON CONFLICT DO NOTHING", (int(u_n), _norm(nueva), int(f['usuario_id'])))
    except Exception as excepcion:
        log.error('reubicar bloqueos %s -> %s falló: %s', ruta_vieja, ruta_nueva, excepcion)
