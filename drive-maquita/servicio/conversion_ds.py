# -*- coding: utf-8 -*-
"""
Conversión de formatos con el Document Server (OnlyOffice).
===========================================================
QUÉ: convierte un archivo del almacén a otro formato usando el conversor que ya
tiene el Document Server (`ConvertService.ashx`), el mismo que se usa para las
miniaturas de Office.

PARA QUÉ, sobre todo: generar la copia SIN MACROS de los formatos antiguos
(.xls, .doc, .ppt, .xlsb). Esos no son ZIP, así que `macros.limpiar()` no puede
quitarles la macro reescribiendo el envase — pero convertirlos al formato
moderno SÍ la elimina: OnlyOffice no soporta VBA, de modo que lo que devuelve
el conversor nunca lleva macro dentro. Aun así, quien llame DEBE verificar el
resultado con `macros.tiene_macros()`: aquí se falla cerrado.

CÓMO: el Document Server descarga el original por la URL pública firmada de
siempre (`/onlyoffice/download?t=<jwt>`), así que hay que pasar el usuario
dueño y la ruta virtual, no la física.

Ver también: macros.py, compartir_macros.py, api_onlyoffice.py
Autoría: Equipo de Tecnología Maquita — 2026-08-04
"""
import logging
import os
import tempfile
import threading
import time

log = logging.getLogger('almacen.conversion_ds')

# El conversor es caro para el Document Server: se limita cuántas conversiones
# simultáneas puede lanzar esta instancia, igual que se hace con las miniaturas.
_SEMAFORO = threading.Semaphore(2)
_ESPERA_SEMAFORO = 15      # segundos esperando turno
_TIEMPO_MAXIMO = 90        # segundos por conversión (documentos grandes)


def disponible():
    """¿Está configurado el Document Server?"""
    try:
        from api_onlyoffice import secreto_ds, url_interna_ds
        return bool(secreto_ds() and url_interna_ds())
    except Exception:
        return False


def convertir(usuario_id, ruta_virtual, extension_destino):
    """Convierte y devuelve la ruta de un archivo TEMPORAL con el resultado.

    `usuario_id` y `ruta_virtual` son los del archivo ORIGINAL (el Document
    Server lo descarga por la URL firmada). Devuelve None si no se pudo
    convertir — nunca lanza: quien llama decide qué hacer sin resultado.
    QUIEN LLAMA debe borrar el temporal cuando termine.
    """
    if not disponible():
        return None
    try:
        import requests
        from api_onlyoffice import (URL_PUBLICA, firmar_jwt, url_interna_ds)
    except Exception as excepcion:
        log.warning('Conversor no disponible: %s', excepcion)
        return None

    origen_ext = (ruta_virtual.rsplit('.', 1)[-1].lower()
                  if '.' in ruta_virtual else '')
    if not origen_ext or not extension_destino:
        return None

    if not _SEMAFORO.acquire(timeout=_ESPERA_SEMAFORO):
        log.info('Conversor ocupado; no se convierte %s', ruta_virtual)
        return None
    try:
        expira = int(time.time()) + 3600
        token_descarga = firmar_jwt({'u': usuario_id, 'r': ruta_virtual,
                                     'uso': 'descarga', 'exp': expira})
        cuerpo = {
            'async': False,
            'filetype': origen_ext,
            'outputtype': extension_destino,
            # La clave identifica la conversión; incluye el momento para que un
            # archivo editado no reciba un resultado cacheado del anterior.
            'key': ('conv%s' % abs(hash((usuario_id, ruta_virtual,
                                         int(time.time()))))) [:20],
            'url': '%s/api/almacen/onlyoffice/download?t=%s' % (URL_PUBLICA,
                                                                token_descarga),
        }
        cuerpo['token'] = firmar_jwt(cuerpo)
        respuesta = requests.post('%s/ConvertService.ashx' % url_interna_ds(),
                                  json=cuerpo,
                                  headers={'Accept': 'application/json'},
                                  timeout=_TIEMPO_MAXIMO)
        datos = respuesta.json()
        url_resultado = datos.get('fileUrl')
        if not url_resultado:
            log.warning('Conversión de %s sin resultado: %s', ruta_virtual, datos)
            return None

        descarga = requests.get(url_resultado, timeout=_TIEMPO_MAXIMO)
        if descarga.status_code != 200 or not descarga.content:
            log.warning('No se pudo bajar el convertido de %s', ruta_virtual)
            return None

        temporal = tempfile.NamedTemporaryFile(prefix='almacen_conv_',
                                              suffix='.' + extension_destino,
                                              delete=False)
        temporal.write(descarga.content)
        temporal.close()
        log.info('Convertido %s → .%s (%s bytes)', ruta_virtual,
                 extension_destino, len(descarga.content))
        return temporal.name
    except Exception as excepcion:
        log.warning('Conversión de %s falló: %s', ruta_virtual, excepcion)
        return None
    finally:
        _SEMAFORO.release()


def copia_sin_macros(usuario_id, ruta_virtual, nombre):
    """Copia sin macros de un formato ANTIGUO (.xls/.doc/.ppt/.xlsb).

    Devuelve `(ruta_temporal, nombre_nuevo)` o `(None, None)`. Se verifica que
    el resultado no lleve macros: si las llevara, se descarta (fail cerrado).
    """
    import macros
    nombre_nuevo = macros.nombre_copia_limpia(nombre)
    destino_ext = macros.extension_de(nombre_nuevo)
    if not destino_ext or destino_ext == macros.extension_de(nombre):
        return None, None

    temporal = convertir(usuario_id, ruta_virtual, destino_ext)
    if not temporal:
        return None, None

    # Comprobación de cierre: el conversor no debería devolver macros nunca,
    # pero esto se apoya en un servicio externo — se verifica igual.
    try:
        if macros.tiene_macros(temporal, nombre_nuevo):
            log.error('El convertido de %s TODAVÍA tiene macros: se descarta',
                      nombre)
            os.unlink(temporal)
            return None, None
    except Exception:
        try:
            os.unlink(temporal)
        except OSError:
            pass
        return None, None

    return temporal, nombre_nuevo
