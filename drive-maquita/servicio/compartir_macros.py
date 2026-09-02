# -*- coding: utf-8 -*-
"""
Política de macros en los ENLACES COMPARTIDOS.
==============================================
QUÉ: al compartir un ARCHIVO, `crear_compartido()` ya impide que salga con la
macro dentro. Faltaba el otro camino: un archivo con macros que está DENTRO de
una CARPETA compartida y se descarga por el enlace (suelto o en el ZIP). Este
módulo cierra ese hueco.

CÓMO: no se bloquea a secas — se entrega la COPIA LIMPIA, igual que ofrece la
web: mismo formato, mismos datos, mismas fórmulas y el mismo formato, sin la
macro. Quien recibe el enlace obtiene un archivo útil; la lógica de negocio de
Maquita no sale de la organización.

Cuando la copia limpia NO se puede generar aquí (formatos antiguos .xls/.doc y
binarios .xlsb, que necesitan conversión del Document Server) se falla CERRADO:
ese archivo no se entrega por el enlace.

Ver también: macros.py (detección y limpieza) y
00-CLAUDE-CONTEXTO/EDICION-REFERENCIAS-Y-MACROS-ONLYOFFICE.md
Autoría: Equipo de Tecnología Maquita — 2026-08-04
"""
import logging
import os
import tempfile

import macros

log = logging.getLogger('almacen.compartir_macros')


def con_macros(ruta_fisica, nombre=None):
    """¿Este archivo lleva macros? Fail cerrado: ante la duda, sí.

    Solo se analizan los formatos ofimáticos; el resto (PDF, imágenes, texto,
    vídeo…) no puede llevar macros y se responde que no sin abrir el archivo.
    """
    nombre = nombre or os.path.basename(ruta_fisica)
    if macros.extension_de(nombre) not in macros.EXTENSIONES_OFIMATICA:
        return False
    try:
        return macros.tiene_macros(ruta_fisica, nombre)
    except Exception as excepcion:
        log.warning('No se pudo analizar macros de %s: %s', nombre, excepcion)
        return True


def entrega_segura(ruta_fisica, nombre=None, usuario_id=None, ruta_virtual=None):
    """Qué entregar por el enlace en lugar de `ruta_fisica`.

    Devuelve `(ruta, nombre, temporal)`:
      - sin macros → el archivo original, `temporal` a None;
      - con macros → una copia limpia en un temporal, con su nombre nuevo;
        QUIEN LLAMA debe borrar `temporal` después de servirlo;
      - no se puede limpiar → `(None, None, None)`: no se entrega.

    `usuario_id` y `ruta_virtual` son los del archivo original: hacen falta para
    los formatos antiguos, que se limpian convirtiéndolos con el Document
    Server. Sin ellos, esos formatos simplemente no se entregan.
    """
    nombre = nombre or os.path.basename(ruta_fisica)
    if not con_macros(ruta_fisica, nombre):
        return ruta_fisica, nombre, None

    if macros.necesita_conversion(nombre):
        # .xls/.doc/.ppt/.xlsb no son ZIP: la macro no se quita reescribiendo
        # el envase. Se convierten al formato moderno con el Document Server,
        # que no soporta VBA y por tanto devuelve el archivo ya sin macro
        # (conversion_ds lo verifica antes de darlo por bueno).
        if usuario_id is None or not ruta_virtual:
            log.info('Enlace: %s tiene macros y no se puede limpiar aquí', nombre)
            return None, None, None
        import conversion_ds
        temporal, nombre_nuevo = conversion_ds.copia_sin_macros(
            usuario_id, ruta_virtual, nombre)
        if not temporal:
            return None, None, None
        return temporal, nombre_nuevo, temporal

    temporal = tempfile.NamedTemporaryFile(prefix='almacen_limpio_', delete=False)
    temporal.close()
    try:
        nombre_limpio = macros.limpiar(ruta_fisica, nombre, temporal.name)
    except Exception as excepcion:
        log.warning('No se pudo limpiar %s: %s', nombre, excepcion)
        nombre_limpio = None
    if not nombre_limpio:
        try:
            os.unlink(temporal.name)
        except OSError:
            pass
        return None, None, None

    log.info('Enlace: se entrega la copia sin macros de %s', nombre)
    return temporal.name, nombre_limpio, temporal.name


def mensaje_bloqueo(nombre):
    """Página breve para el invitado cuando el archivo no se puede entregar."""
    return (
        '<div style="font-family:Arial,sans-serif;max-width:460px;'
        'margin:90px auto;text-align:center;color:#202124">'
        '<h3>Este archivo no se puede descargar</h3>'
        '<p style="color:#5f6368;line-height:1.5">«%s» contiene macros, que son '
        'de uso interno de la Fundación Maquita y no salen por un enlace '
        'compartido.</p>'
        '<p style="color:#5f6368;line-height:1.5">Si necesitas su contenido, '
        'pídeselo a quien te compartió el enlace.</p></div>'
        % (nombre,)
    )
