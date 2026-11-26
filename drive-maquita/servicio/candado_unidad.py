# -*- coding: utf-8 -*-
"""Candado de una unidad compartida (16/11/2026).

Pedido de Wilson para la unidad 16 «Encuestas»: «si borran se dañan los datos; ni siquiera yo debería poder borrar
datos, carpetas ni editarlos». Con el candado puesto, NADIE (tampoco administradores de la unidad ni master) puede,
desde el Drive o el disco de red:
  · enviar a la papelera, mover, renombrar ni restaurar versiones de lo que hay dentro;
  · reemplazar un archivo que ya existe al subir otro con el mismo nombre;
  · editar a mano en OnlyOffice (se abre en solo lectura);
  · escribir nada por el disco montado (WebDAV).
Sí se puede: ver, descargar, crear carpetas y archivos NUEVOS (así se crean las encuestas nuevas) y lo que hace el
sistema por sus vías propias: el editor de encuestas guarda su .forma y el Excel de resultados se actualiza solo.
Quitar el candado es una decisión de Tecnología: `quitar()` desde el servidor, con motivo; queda el historial.

Sin Flask a propósito: lo usan la web y el servicio WebDAV (otro proceso)."""
import logging
import time

from almacen_bd import consultar, ejecutar

log = logging.getLogger('almacen.candado_unidad')
MENSAJE = ('Esta unidad está protegida: nadie puede borrar, mover, renombrar ni reemplazar su contenido, '
           'tampoco los administradores. Las encuestas y sus resultados se actualizan solos desde Datos de campo. '
           'Si necesita un cambio, pídalo a Tecnología.')
_DDL = """
CREATE TABLE IF NOT EXISTS unidad_candados (
    id          BIGSERIAL PRIMARY KEY,
    unidad_id   INTEGER NOT NULL,
    motivo      TEXT,
    puesto_por  INTEGER,
    puesto_en   TIMESTAMPTZ NOT NULL DEFAULT now(),
    quitado_por INTEGER,
    quitado_en  TIMESTAMPTZ,
    motivo_quitar TEXT
);
CREATE INDEX IF NOT EXISTS ix_unidad_candados_vivos ON unidad_candados (unidad_id) WHERE quitado_en IS NULL;
"""
_cache = {'cuando': 0.0, 'cerradas': frozenset()}
_SEGUNDOS = 30


def instalar():
    ejecutar(_DDL)


def cerradas():
    """{unidad_id} con candado vigente (caché de 30 s; ante un fallo de BD se usa lo último conocido)."""
    ahora = time.time()
    if ahora - _cache['cuando'] > _SEGUNDOS:
        try:
            filas = consultar('SELECT DISTINCT unidad_id FROM unidad_candados WHERE quitado_en IS NULL')
            _cache['cerradas'] = frozenset(int(f['unidad_id']) for f in filas)
        except Exception as excepcion:
            log.warning('No se pudo leer el candado de unidades (se usa lo último conocido): %s', excepcion)
        _cache['cuando'] = ahora
    return _cache['cerradas']


def unidad_cerrada(ruta_virtual):
    """unidad_id si la ruta está dentro de una unidad con candado; si no, None."""
    from seguridad_rutas import unidad_de_ruta
    try:
        unidad_id, _ = unidad_de_ruta(ruta_virtual or '/')
    except Exception:
        return None
    return unidad_id if unidad_id is not None and int(unidad_id) in cerradas() else None


def exigir_abierta(ruta_virtual, accion=''):
    """Lanza RutaInvalida (403) si la ruta está en una unidad con candado."""
    unidad_id = unidad_cerrada(ruta_virtual)
    if unidad_id is not None:
        from seguridad_rutas import RutaInvalida
        log.info('Candado: se impidió «%s» en %s', accion, ruta_virtual)
        raise RutaInvalida(MENSAJE, codigo=403)


def poner(unidad_id, por, motivo):
    instalar()
    if int(unidad_id) not in {int(f['unidad_id']) for f in consultar(
            'SELECT unidad_id FROM unidad_candados WHERE quitado_en IS NULL')}:
        ejecutar('INSERT INTO unidad_candados (unidad_id, motivo, puesto_por) VALUES (%s, %s, %s)',
                 (int(unidad_id), motivo, por))
    _cache['cuando'] = 0.0


def quitar(unidad_id, por, motivo):
    if not (motivo or '').strip():
        raise ValueError('Escriba el motivo para quitar el candado.')
    ejecutar("""UPDATE unidad_candados SET quitado_en = now(), quitado_por = %s, motivo_quitar = %s
                WHERE unidad_id = %s AND quitado_en IS NULL""", (por, motivo, int(unidad_id)))
    _cache['cuando'] = 0.0
