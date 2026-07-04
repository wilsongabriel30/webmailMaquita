# -*- coding: utf-8 -*-
"""
Registro de actividad del Almacén Maquita.
==========================================
Guarda un rastro de las acciones (subió, borró, compartió, renombró, restauró...)
para la "Actividad reciente" estilo Google Drive y para auditoría.
Módulo de bajo nivel (solo depende de almacen_bd) para no crear ciclos de import.

Autoría: Equipo de Tecnología Maquita — 2026-07-03
"""
import logging

from almacen_bd import ejecutar

log = logging.getLogger('almacen.registro')


def registrar_actividad(usuario_id, accion, ruta='', detalle=''):
    """Anota una acción. FAIL-SILENT: la actividad nunca debe romper la operación real."""
    try:
        ejecutar("""
            INSERT INTO actividad (usuario_id, accion, ruta, detalle)
            VALUES (%s, %s, %s, %s)
        """, (int(usuario_id), str(accion)[:30], str(ruta or '')[:1000], str(detalle or '')[:500]))
    except Exception as excepcion:
        log.debug('No se pudo registrar actividad: %s', excepcion)
