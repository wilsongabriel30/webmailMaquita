# -*- coding: utf-8 -*-
"""
Edición en línea de formatos ANTIGUOS (.doc, .xls, .ppt, .xlsb…)
================================================================
QUÉ: el editor (OnlyOffice) solo permite EDITAR los formatos modernos
(.docx/.xlsx/.pptx…); los antiguos se abren en modo lectura. Un usuario que
sube un .doc a su unidad no podía trabajar con él en línea (caso reportado el
02/09/2026 en Drive Maquita).

CÓMO (igual que Google Drive, sin duplicados): cuando alguien CON permiso de
escritura abre un formato antiguo, se convierte al formato moderno con el
conversor del Document Server (ConvertService.ashx), el resultado se guarda
EN LA MISMA CARPETA con el mismo nombre y la extensión nueva (pasa por
nucleo.subir: índice, dedup, versiones, cuota) y el editor abre ESE archivo.
El original va a la PAPELERA (recuperable): el usuario ve un solo archivo.

- Si la copia moderna ya existe y es más reciente que el original, se reutiliza
  (y el original, si sigue en la carpeta, va a la papelera).
- Si el original es más nuevo (lo volvieron a subir), se reconvierte; la copia
  anterior queda como VERSIÓN (historial normal del Almacén).
- Si el conversor falla o no está, no pasa nada: el archivo se abre en modo
  lectura, como antes. Aquí NUNCA se lanza.

QUIÉN LLAMA: api_onlyoffice.onlyoffice_config (solo con sesión; los enlaces
públicos no convierten).
Autoría: Equipo de Tecnología Maquita — 2026-09-02
"""
import logging
import os
import tempfile
import threading
import time

log = logging.getLogger('almacen.conversion_edicion')

# Formato antiguo → moderno editable (OLE y binarios que OnlyOffice no edita).
CONVERTIBLES = {
    'doc': 'docx', 'dot': 'dotx',
    'xls': 'xlsx', 'xlt': 'xltx', 'xlsb': 'xlsx',
    'ppt': 'pptx', 'pot': 'potx',
}

# El conversor es caro para el Document Server: pocas conversiones a la vez.
_SEMAFORO = threading.Semaphore(2)
_ESPERA_SEMAFORO = 15
_TIEMPO_MAXIMO = 90


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


def _convertir(usuario_id: int, ruta_virtual: str, extension_destino: str):
    """Convierte con el Document Server y devuelve un archivo TEMPORAL (o None)."""
    try:
        import requests
        from api_onlyoffice import URL_PUBLICA, firmar_jwt, secreto_ds, url_interna_ds
        if not (secreto_ds() and url_interna_ds()):
            return None
    except Exception as excepcion:
        log.warning('Conversor no disponible: %s', excepcion)
        return None
    if not _SEMAFORO.acquire(timeout=_ESPERA_SEMAFORO):
        log.info('Conversor ocupado; no se convierte %s', ruta_virtual)
        return None
    try:
        expira = int(time.time()) + 3600
        token = firmar_jwt({'u': usuario_id, 'r': ruta_virtual, 'uso': 'descarga', 'exp': expira})
        cuerpo = {
            'async': False,
            'filetype': extension_de(ruta_virtual),
            'outputtype': extension_destino,
            'key': ('conv%s' % abs(hash((usuario_id, ruta_virtual, int(time.time())))))[:20],
            'url': '%s/api/almacen/onlyoffice/download?t=%s' % (URL_PUBLICA, token),
        }
        cuerpo['token'] = firmar_jwt(cuerpo)
        respuesta = requests.post('%s/ConvertService.ashx' % url_interna_ds(), json=cuerpo,
                                  headers={'Accept': 'application/json'}, timeout=_TIEMPO_MAXIMO)
        datos = respuesta.json()
        url_resultado = datos.get('fileUrl')
        if not url_resultado:
            log.warning('Conversión de %s sin resultado: %s', ruta_virtual, datos)
            return None
        descarga = requests.get(url_resultado, timeout=_TIEMPO_MAXIMO)
        if descarga.status_code != 200 or not descarga.content:
            return None
        temporal = tempfile.NamedTemporaryFile(prefix='almacen_conv_', suffix='.' + extension_destino,
                                              delete=False)
        temporal.write(descarga.content)
        temporal.close()
        return temporal.name
    except Exception as excepcion:
        log.warning('Conversión de %s falló: %s', ruta_virtual, excepcion)
        return None
    finally:
        _SEMAFORO.release()


def _retirar_original(usuario_id: int, ruta_virtual: str) -> None:
    """Manda el formato antiguo a la papelera (recuperable). FAIL-SILENT."""
    try:
        from nucleo_archivos import enviar_a_papelera
        enviar_a_papelera(usuario_id, ruta_virtual)
        log.info('Original antiguo %s enviado a la papelera (usuario %s)', ruta_virtual, usuario_id)
    except Exception as excepcion:
        log.warning('No se pudo retirar el original %s: %s', ruta_virtual, excepcion)


def preparar_para_editar(usuario_id: int, ruta_virtual: str, fisica_original: str):
    """Devuelve (ruta_a_abrir, convertido_ahora). Nunca lanza."""
    try:
        ruta_nueva = ruta_moderna(ruta_virtual)
        if not ruta_nueva:
            return ruta_virtual, False

        from nucleo_archivos import subir
        from seguridad_rutas import ruta_fisica
        fisica_nueva = ruta_fisica(usuario_id, ruta_nueva)
        if (os.path.isfile(fisica_nueva)
                and os.path.getmtime(fisica_nueva) >= os.path.getmtime(fisica_original)):
            _retirar_original(usuario_id, ruta_virtual)
            return ruta_nueva, False

        temporal = _convertir(usuario_id, ruta_virtual, extension_de(ruta_nueva))
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
