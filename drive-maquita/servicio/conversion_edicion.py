# -*- coding: utf-8 -*-
"""
Edición en línea de formatos ANTIGUOS (.doc, .xls, .ppt, .xlsb…)
================================================================
QUÉ: el editor (OnlyOffice) solo permite EDITAR los formatos modernos
(.docx/.xlsx/.pptx…); los antiguos se abren en modo lectura. Hasta el
02/09/2026 un usuario que subía un .doc a su unidad no podía trabajar con
él en línea (caso reportado en /archivos-almacen/M17).

CÓMO (igual que Google Drive): cuando alguien CON permiso de escritura abre
un formato antiguo, se convierte al formato moderno con el conversor del
Document Server (conversion_ds.convertir), el resultado se guarda EN LA
MISMA CARPETA con el mismo nombre y la extensión nueva (pasa por
nucleo.subir: índice, dedup, versiones, cuota) y el editor abre ESE archivo.
El original NO queda duplicado en la carpeta: se manda a la PAPELERA
(recuperable), así el usuario ve un solo archivo, como en Google Drive.

- Si la copia moderna ya existe y es más reciente que el original, se reutiliza
  (y el original, si sigue en la carpeta, va a la papelera).
- Si el original es más nuevo (lo volvieron a subir), se reconvierte; la
  copia anterior queda como VERSIÓN del .docx (historial normal del Almacén).
- Si el conversor falla o no está, no pasa nada: el archivo se abre en modo
  lectura, como antes. Aquí NUNCA se lanza.

QUIÉN LLAMA: api_onlyoffice.onlyoffice_config (solo con sesión; los enlaces
públicos no convierten).
Autoría: Equipo de Tecnología Maquita — 2026-09-02
"""
import logging
import os

log = logging.getLogger('almacen.conversion_edicion')

# Formato antiguo → moderno editable. Se toma de macros.py para no duplicar
# la lista; si ese módulo faltara, se usa el mínimo conocido.
try:
    from macros import FORMATOS_ANTIGUOS, FORMATOS_BINARIOS
    CONVERTIBLES = dict(FORMATOS_ANTIGUOS)
    CONVERTIBLES.update(FORMATOS_BINARIOS)
except Exception:                       # pragma: no cover
    CONVERTIBLES = {'doc': 'docx', 'xls': 'xlsx', 'ppt': 'pptx', 'xlsb': 'xlsx'}


def extension_de(ruta_virtual: str) -> str:
    nombre = ruta_virtual.rsplit('/', 1)[-1]
    return nombre.rsplit('.', 1)[-1].lower() if '.' in nombre else ''


def es_convertible(extension: str) -> bool:
    return extension in CONVERTIBLES


def ruta_moderna(ruta_virtual: str):
    """'/M17/Informe.doc' → '/M17/Informe.docx' (None si no es formato antiguo)."""
    extension = extension_de(ruta_virtual)
    destino = CONVERTIBLES.get(extension)
    if not destino:
        return None
    return ruta_virtual[: -len(extension)] + destino


def _retirar_original(usuario_id: int, ruta_virtual: str) -> None:
    """Manda el formato antiguo a la papelera (recuperable). FAIL-SILENT."""
    try:
        from nucleo_archivos import enviar_a_papelera
        enviar_a_papelera(usuario_id, ruta_virtual)
        log.info('Original antiguo %s enviado a la papelera (usuario %s)', ruta_virtual, usuario_id)
    except Exception as excepcion:
        log.warning('No se pudo retirar el original %s: %s', ruta_virtual, excepcion)


def preparar_para_editar(usuario_id: int, ruta_virtual: str, fisica_original: str):
    """Devuelve (ruta_a_abrir, convertido_ahora).

    - ruta_a_abrir == ruta_virtual  → no se pudo/necesitó convertir (abrir como venía).
    - convertido_ahora True         → se acaba de crear la copia moderna.
    Nunca lanza.
    """
    try:
        ruta_nueva = ruta_moderna(ruta_virtual)
        if not ruta_nueva:
            return ruta_virtual, False

        from nucleo_archivos import ruta_fisica, subir
        fisica_nueva = ruta_fisica(usuario_id, ruta_nueva)
        if (os.path.isfile(fisica_nueva)
                and os.path.getmtime(fisica_nueva) >= os.path.getmtime(fisica_original)):
            _retirar_original(usuario_id, ruta_virtual)
            return ruta_nueva, False          # ya hay copia moderna vigente

        import conversion_ds
        if not conversion_ds.disponible():
            return ruta_virtual, False
        extension_nueva = extension_de(ruta_nueva)
        temporal = conversion_ds.convertir(usuario_id, ruta_virtual, extension_nueva)
        if not temporal:
            log.warning('No se pudo convertir %s para editar (usuario %s): se abre en lectura',
                        ruta_virtual, usuario_id)
            return ruta_virtual, False
        try:
            carpeta = ruta_virtual.rsplit('/', 1)[0] or '/'
            nombre_nuevo = ruta_nueva.rsplit('/', 1)[-1]
            with open(temporal, 'rb') as flujo:
                subir(usuario_id, carpeta, nombre_nuevo, flujo)
        finally:
            try:
                os.unlink(temporal)
            except OSError:
                pass

        _retirar_original(usuario_id, ruta_virtual)
        try:
            from registro import registrar_actividad
            registrar_actividad(usuario_id, 'convirtio', ruta_nueva, ruta_virtual)
        except Exception:
            pass
        log.info('Convertido para editar: %s → %s (usuario %s)', ruta_virtual, ruta_nueva, usuario_id)
        return ruta_nueva, True
    except Exception as excepcion:
        log.warning('Conversión para editar de %s falló: %s', ruta_virtual, excepcion)
        return ruta_virtual, False
