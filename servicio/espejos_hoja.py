# -*- coding: utf-8 -*-
"""
Copia fiel de una hoja en su propio archivo (Drive Maquita)
===========================================================
«Extraer una hoja…» con «Mantener actualizado» dejaba un vínculo de datos: solo
el BLOQUE de la tabla viajaba, y solo sus valores. Un título nuevo en la hoja
original, el formato, o filas y columnas fuera de ese bloque no llegaban a la
copia (23/09/2026). Lo que se pedía es otra cosa: tener la hoja aparte y que
TODO lo que pase en la original se vea en la copia.

Un «espejo» hace exactamente eso: cada vez que el libro de origen cambia (se
guarda desde el editor, llega una respuesta del formulario, se sube encima), el
archivo de destino se REHACE a partir de la hoja completa con
`hoja_a_archivo.extraer` —formato, celdas combinadas, tabla, imagen, título— y
con las fórmulas cambiadas por su resultado; o (28/09/2026) conservando las
fórmulas de la propia hoja, o todas con las hojas de las que beben, ocultas.

La copia es de solo lectura en la práctica: si alguien la edita, su cambio se
pierde en el siguiente refresco. Si se guardó desde el editor por encima del
espejo, al cerrarse se vuelve a poner la copia fiel (`refrescar_por_destino`).

Se engancha en los mismos puntos que los vínculos de datos
(`api_vinculos.refrescar_por_origen` / `refrescar_por_destino` / actualizar).

Rutas (montadas sobre bp_vinculos, mismo prefijo /api/almacen):
  POST /espejos/eliminar {id}   — deja de actualizarse (el archivo se queda)

Autoría: Equipo de Tecnología Maquita — 2026-09-23
"""
import hashlib
import io
import logging
import os

import almacen_bd as bd
import hoja_a_archivo as extractor
from seguridad_rutas import normalizar_ruta_virtual, ruta_fisica

log = logging.getLogger('almacen.espejos')

_esquema_listo = False


def asegurar_esquema():
    """Crea la tabla de espejos si no existe. Idempotente."""
    global _esquema_listo
    if _esquema_listo:
        return
    bd.ejecutar("""
        CREATE TABLE IF NOT EXISTS espejos_hoja (
            id              SERIAL PRIMARY KEY,
            origen_usuario  INTEGER NOT NULL,
            origen_ruta     TEXT NOT NULL,
            origen_hoja     TEXT NOT NULL,
            destino_usuario INTEGER NOT NULL,
            destino_ruta    TEXT NOT NULL,
            creado_por      INTEGER,
            creado_en       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            actualizado_en  TIMESTAMPTZ,
            huella          TEXT,          -- sha256 de lo último que se escribió
            ultimo_error    TEXT,
            activo          BOOLEAN NOT NULL DEFAULT TRUE
        );
        CREATE INDEX IF NOT EXISTS ix_espejos_origen
            ON espejos_hoja(origen_ruta) WHERE activo;
        CREATE INDEX IF NOT EXISTS ix_espejos_destino
            ON espejos_hoja(destino_ruta) WHERE activo;
        -- 28/09/2026: qué lleva la copia: 'valores', 'propias' (sus
        -- fórmulas de cálculo) o 'formulas' (todas, con hojas de origen ocultas).
        ALTER TABLE espejos_hoja ADD COLUMN IF NOT EXISTS
            contenido TEXT NOT NULL DEFAULT 'valores';
    """)
    _esquema_listo = True


def _huella(datos):
    return hashlib.sha256(datos).hexdigest()


# La copia abierta en el editor se entera de que cambió por esta marca
# (api_espejos_vivo, 28/09/2026). En una unidad la ruta es de todos; en el
# espacio personal, de su dueño.
HORAS_MARCA = 12


def _clave_marca(usuario, ruta):
    return 'espejo:%s:%s' % ('unidad' if ruta.startswith('/unidades/') else int(usuario), ruta)


def marca_de(usuario, ruta):
    import avisos_redis
    return avisos_redis.leer(_clave_marca(usuario, ruta))


def _marcar(usuario, ruta, huella):
    import time
    import avisos_redis
    avisos_redis.poner(_clave_marca(usuario, ruta), '%s-%d' % (huella[:12], int(time.time())),
                       HORAS_MARCA * 3600)


def _huella_disco(usuario, ruta):
    try:
        with open(ruta_fisica(usuario, ruta), 'rb') as f:
            return _huella(f.read())
    except OSError:
        return None


def _puede_leer(e):
    import api_vinculos
    return api_vinculos.puede_leer(e['destino_usuario'], e['origen_usuario'],
                                   e['origen_ruta'])


def _aplicar(e, contenido_origen=None, forzar=False):
    """Rehace UN espejo. Devuelve (ok, mensaje). Nunca lanza.

    Solo escribe si hace falta: si lo que saldría es lo que ya hay en disco no
    se crea una versión nueva (cada respuesta dispara esto).
    """
    try:
        if not _puede_leer(e):
            raise PermissionError('Ya no tienes permiso sobre el archivo de origen')
        if contenido_origen is None:
            with open(ruta_fisica(e['origen_usuario'], e['origen_ruta']), 'rb') as f:
                contenido_origen = f.read()
        nuevo = extractor.extraer(contenido_origen, e['origen_hoja'],
                                  que=e.get('contenido') or 'valores')
        huella = _huella(nuevo)
        if not forzar and huella == e.get('huella') and \
                _huella_disco(e['destino_usuario'], e['destino_ruta']) == huella:
            return True, 'al día'
        import nucleo_archivos as nucleo
        carpeta, _, nombre = e['destino_ruta'].rpartition('/')
        nucleo.subir(e['destino_usuario'], carpeta or '/', nombre, io.BytesIO(nuevo))
        # Quien lo abra después debe ver esta copia, no la que guarda el editor.
        try:
            from api_onlyoffice import invalidar_cache
            invalidar_cache(e['destino_usuario'], e['destino_ruta'])
        except Exception as exc:
            log.warning('espejo %s: no se pudo refrescar el editor (%s)', e['id'], exc)
        bd.ejecutar('UPDATE espejos_hoja SET actualizado_en = NOW(), huella = %s, '
                    'ultimo_error = NULL WHERE id = %s', (huella, e['id']))
        _marcar(e['destino_usuario'], e['destino_ruta'], huella)
        return True, 'ok'
    except Exception as exc:
        motivo = ('La hoja «%s» ya no existe en el origen' % e['origen_hoja']
                  if isinstance(exc, extractor.SinLaHoja) else str(exc))
        log.warning('espejo %s (%s → %s): %s', e.get('id'), e.get('origen_ruta'),
                    e.get('destino_ruta'), motivo)
        try:
            bd.ejecutar('UPDATE espejos_hoja SET ultimo_error = %s WHERE id = %s',
                        (motivo[:500], e['id']))
        except Exception:
            pass
        return False, motivo


def crear(usuario, origen, hoja, destino, que='valores'):
    """Registra el espejo y lo aplica ya. Devuelve (ok, mensaje)."""
    asegurar_esquema()
    fila = bd.ejecutar(
        """INSERT INTO espejos_hoja (origen_usuario, origen_ruta, origen_hoja,
                                     destino_usuario, destino_ruta, creado_por,
                                     contenido)
           VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING *""",
        (usuario, normalizar_ruta_virtual(origen), hoja,
         usuario, normalizar_ruta_virtual(destino), usuario, que))
    return _aplicar(dict(fila), forzar=True)


def _filas(columna, usuario, ruta, extra=''):
    # En el espacio personal las rutas se repiten entre personas: cuenta el
    # dueño. En una unidad la ruta es la misma para todos sus miembros.
    asegurar_esquema()
    return [dict(f) for f in bd.consultar(
        'SELECT * FROM espejos_hoja WHERE activo AND {c}_ruta = %s '
        'AND ({c}_usuario = %s OR {c}_ruta LIKE %s) {extra} ORDER BY id'
        .format(c=columna, extra=extra), (ruta, int(usuario), '/unidades/%'))]


def refrescar_por_origen(usuario, ruta):
    """Cambió el libro de origen: se rehacen sus espejos. Nunca lanza."""
    try:
        ruta = normalizar_ruta_virtual(ruta)
        filas = _filas('origen', usuario, ruta, 'AND origen_ruta <> destino_ruta')
        if not filas:
            return 0
        with open(ruta_fisica(filas[0]['origen_usuario'], ruta), 'rb') as f:
            contenido = f.read()         # se lee UNA vez para todas las copias
        n = sum(1 for e in filas if _aplicar(e, contenido)[0])
        log.info('espejos de %s: %s/%s al día', ruta, n, len(filas))
        return n
    except Exception as exc:
        log.warning('espejos por origen %s: %s', ruta, exc)
        return 0


def refrescar_por_destino(usuario, ruta, forzar=False):
    """Se cerró (o se pidió actualizar) una copia: si alguien la cambió,
    vuelve a ser fiel al original. Nunca lanza."""
    try:
        ruta = normalizar_ruta_virtual(ruta)
        filas = _filas('destino', usuario, ruta)
        return sum(1 for e in filas if _aplicar(e, forzar=forzar)[0])
    except Exception as exc:
        log.warning('espejos por destino %s: %s', ruta, exc)
        return 0


def mapa(usuario, ruta):
    """(entrantes, salientes) con el mismo formato que las fichas de vínculos."""
    asegurar_esquema()

    def ficha(f, mio):
        return {
            'id': f['id'], 'tipo': 'espejo',
            'origen_ruta': f['origen_ruta'],
            'origen_nombre': f['origen_ruta'].rsplit('/', 1)[-1],
            'origen_hoja': f['origen_hoja'],
            'origen_rango': {'propias': 'hoja completa, con sus fórmulas',
                             'formulas': 'hoja completa, con fórmulas y hojas de origen'}
                            .get(f.get('contenido'), 'hoja completa'),
            'destino_ruta': f['destino_ruta'],
            'destino_nombre': f['destino_ruta'].rsplit('/', 1)[-1],
            'destino_hoja': f['origen_hoja'], 'destino_celda': 'copia fiel',
            'actualizado_en': f['actualizado_en'].isoformat() if f['actualizado_en'] else '',
            'error': f.get('ultimo_error') or '',
            'mio': bool(mio),
        }
    entrantes = bd.consultar(
        'SELECT * FROM espejos_hoja WHERE activo AND destino_ruta = %s '
        'AND (destino_usuario = %s OR destino_ruta LIKE %s) ORDER BY id',
        (ruta, usuario, '/unidades/%'))
    salientes = bd.consultar(
        'SELECT * FROM espejos_hoja WHERE activo AND origen_ruta = %s ORDER BY id',
        (ruta,))
    return ([ficha(f, True) for f in entrantes],
            [ficha(f, f['destino_usuario'] == usuario) for f in salientes])


def obtener(espejo_id):
    asegurar_esquema()
    filas = bd.consultar('SELECT * FROM espejos_hoja WHERE id = %s AND activo',
                         (int(espejo_id),))
    return dict(filas[0]) if filas else None


def desactivar(espejo_id):
    """Deja de actualizar la copia. El archivo se queda como está."""
    bd.ejecutar('UPDATE espejos_hoja SET activo = FALSE WHERE id = %s',
                (int(espejo_id),))
