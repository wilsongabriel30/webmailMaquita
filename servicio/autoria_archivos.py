# -*- coding: utf-8 -*-
"""
¿Quién subió (o creó) este archivo o carpeta?
=============================================
17/09/2026. Pedido de Wilson: en una unidad compartida, un editor puede
MOVER lo que él mismo subió, sin ser administrador de la unidad
(ver permisos_mover.puede_mover_lo_propio).

El Almacén no guarda un «dueño» por archivo: cada archivo vive en la carpeta
de la unidad. Lo que sí hay es el registro `actividad`, que anota cada subida,
carpeta creada, copia, movimiento y renombrado CON la ruta de antes. Con eso
se reconstruye la historia de una ruta hacia atrás hasta su origen:

    movio / renombro / convirtio   → la ruta venía de `detalle`; seguir desde ahí
    subio / creo_carpeta / copio   → ESE usuario lo creó: es el autor

Si el elemento no tiene historia propia, puede que lo moviera o renombrara una
carpeta superior (mover «A» lleva dentro a «A/informe.pdf» sin anotar nada del
informe): se busca el cambio en la carpeta superior más cercana y se reconstruye
la ruta antigua.

Ante cualquier duda —historia cortada (p. ej. algo movido por el disco de red,
que no anota actividad), bucle, demasiados saltos— la respuesta es «no se sabe»
y quien llama debe NO permitir: es preferible pedir ayuda a un administrador que
mover lo de otra persona.

Autoría: Equipo de Tecnología Maquita — 2026-09-17
"""
import logging
import os

from almacen_bd import consultar

log = logging.getLogger('almacen.autoria')

CREACION = ('subio', 'creo_carpeta', 'copio')
TRASLADO = ('movio', 'renombro', 'convirtio')
MAX_SALTOS = 60
MAX_ELEMENTOS_CARPETA = 400


def _ultimo_evento(ruta, hasta):
    """Evento más reciente (creación o traslado) que dejó algo en `ruta`."""
    filas = consultar(
        """SELECT usuario_id, accion, detalle, creado_en FROM actividad
            WHERE ruta = %s AND accion = ANY(%s)
              AND (%s::timestamptz IS NULL OR creado_en <= %s::timestamptz)
            ORDER BY creado_en DESC, id DESC LIMIT 1""",
        (ruta, list(CREACION + TRASLADO), hasta, hasta))
    return filas[0] if filas else None


def _traslado_de_superior(ruta, hasta):
    """Movimiento/renombrado más cercano de una carpeta que contiene a `ruta`.

    Devuelve (evento, prefijo) de la carpeta superior MÁS PROFUNDA con un
    traslado (o creación por copia) anterior a `hasta`, o (None, None).
    """
    partes = ruta.rstrip('/').split('/')
    # /unidades/<id> no se mueve: se para en el primer nivel dentro de la unidad.
    for corte in range(len(partes) - 1, 3, -1):
        prefijo = '/'.join(partes[:corte])
        filas = consultar(
            """SELECT usuario_id, accion, detalle, creado_en FROM actividad
                WHERE ruta = %s AND accion = ANY(%s)
                  AND (%s::timestamptz IS NULL OR creado_en <= %s::timestamptz)
                ORDER BY creado_en DESC, id DESC LIMIT 1""",
            (prefijo, list(TRASLADO + ('copio',)), hasta, hasta))
        if filas:
            return filas[0], prefijo
    return None, None


def autor_de(ruta):
    """ID de quien subió/creó lo que hoy está en `ruta`, o None si no se sabe."""
    actual = (ruta or '').rstrip('/')
    hasta = None
    vistas = set()
    try:
        for _ in range(MAX_SALTOS):
            clave = (actual, str(hasta))
            if clave in vistas:
                return None
            vistas.add(clave)

            evento = _ultimo_evento(actual, hasta)
            if evento:
                if evento['accion'] in CREACION:
                    return int(evento['usuario_id'])
                if not evento['detalle']:
                    return None
                actual = evento['detalle'].rstrip('/')
                hasta = evento['creado_en']
                continue

            superior, prefijo = _traslado_de_superior(actual, hasta)
            if not superior:
                return None
            if superior['accion'] == 'copio':
                # La carpeta superior llegó copiada: todo lo de dentro lo creó quien copió.
                return int(superior['usuario_id'])
            if not superior['detalle']:
                return None
            actual = superior['detalle'].rstrip('/') + actual[len(prefijo):]
            hasta = superior['creado_en']
        return None
    except Exception as excepcion:
        log.warning('no se pudo reconstruir la autoría de %r: %s', ruta, excepcion)
        return None


def es_autor(usuario_id, ruta):
    return autor_de(ruta) == int(usuario_id)


def carpeta_toda_propia(usuario_id, ruta_virtual, ruta_fisica):
    """¿La carpeta y TODO lo que contiene lo subió/creó esta persona?

    Mover una carpeta arrastra lo de dentro: si hay algo de otra persona, no.
    Con más de MAX_ELEMENTOS_CARPETA elementos se responde que no (y el aviso
    pide a un administrador), para no revisar miles de rutas en cada arrastre.
    """
    if not es_autor(usuario_id, ruta_virtual):
        return False
    revisados = 0
    base = ruta_virtual.rstrip('/')
    for raiz, carpetas, archivos in os.walk(ruta_fisica):
        carpetas[:] = [c for c in carpetas if not c.startswith('.')]
        relativa = os.path.relpath(raiz, ruta_fisica)
        prefijo = base if relativa == '.' else base + '/' + relativa.replace(os.sep, '/')
        for nombre in carpetas + [a for a in archivos if not a.startswith('.')]:
            revisados += 1
            if revisados > MAX_ELEMENTOS_CARPETA:
                return False
            if not es_autor(usuario_id, prefijo + '/' + nombre):
                return False
    return True
